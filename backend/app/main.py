import io
import json
import os
import time
import logging
import httpx
from collections import defaultdict, deque
from contextlib import asynccontextmanager
from typing import Literal

import numpy as np
import pandas as pd
from fastapi import FastAPI, Depends, HTTPException, UploadFile, File, Form, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, Field, ConfigDict
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from .core import Base, engine, db, current_user, roles, hasher, token, audit, now
from .models import User, Customer, Dataset, Transaction, ModelVersion, Prediction, Segment, Strategy, Campaign, CampaignCustomer, Outcome, Execution, ToolCall, Audit, Report, Setting
from .data import ingest, demo
from .ml import train, predict, latest_model, latest_predictions, customer_prediction
from .intelligence import Registry, AGENTS, POLICY, customer, segment_one, campaign_performance, start_workflow, workflow, assistant

@asynccontextmanager
async def lifespan(app):
    if os.getenv('ENVIRONMENT') != 'production': Base.metadata.create_all(engine)
    from .admin import bootstrap_admin
    from .core import SessionLocal
    with SessionLocal() as session:
        bootstrap_admin(session)
    yield

app = FastAPI(title='RetainIQ AI', version='1.0.0', lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=os.getenv('CORS_ORIGINS', 'http://localhost:5174,http://127.0.0.1:5174').split(','), allow_credentials=True, allow_methods=['GET', 'POST', 'PUT'], allow_headers=['Authorization', 'Content-Type'])
limits = defaultdict(deque)

@app.middleware('http')
async def guard(request: Request, call_next):
    ip = request.client.host if request.client else 'unknown'
    key = (ip, 'auth' if request.url.path.startswith('/api/auth') else 'api')
    bucket = limits[key]
    t = time.monotonic()
    while bucket and bucket[0] < t - 60: bucket.popleft()
    if len(bucket) >= (30 if key[1] == 'auth' else 300): return JSONResponse({'detail': 'Rate limit reached. Try again in a minute.'}, status_code=429)
    bucket.append(t)
    if int(request.headers.get('content-length', '0')) > 10 * 1024 * 1024: return JSONResponse({'detail': 'Upload exceeds 10 MB'}, status_code=413)
    response = await call_next(request)
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['Cache-Control'] = 'no-store'
    return response

@app.exception_handler(Exception)
async def safe_error(request, exc):
    logging.exception('Unhandled application failure')
    return JSONResponse({'detail': 'The operation failed. Review server logs; no success was recorded.'}, status_code=500)

class Input(BaseModel):
    model_config = ConfigDict(extra='forbid')

class Credentials(Input):
    email: str = Field(min_length=5, max_length=200, pattern=r'^[^\s@]+@[^\s@]+\.[^\s@]+$')
    password: str = Field(min_length=10, max_length=200)

class DatasetInput(Input):
    dataset_id: str

class CustomerInput(Input):
    customer_id: str = Field(min_length=1, max_length=100)

class BatchInput(Input):
    customer_ids: list[str] | None = Field(None, max_length=500)

class Approval(Input):
    kind: Literal['strategy', 'campaign', 'execution']
    id: str
    approved: bool

class CampaignInput(Input):
    name: str = Field(min_length=3, max_length=200)
    channel: Literal['email', 'internal'] = 'email'
    customer_ids: list[str] = Field(min_length=1, max_length=500)

class OutcomeInput(CustomerInput):
    retained: bool
    cost: float = Field(ge=0, le=1e8)
    evidence: str = Field(min_length=10, max_length=2000)
    observed_at: str

class Question(Input):
    question: str = Field(min_length=3, max_length=2000)
    customer_id: str | None = None

class RiskSettings(Input):
    medium: float = Field(ge=.01, le=.98)
    high: float = Field(ge=.02, le=.99)

class ReportInput(Input):
    title: str = Field(default='Retention intelligence report', min_length=3, max_length=200)

class RoleInput(Input):
    role: Literal['admin', 'analyst', 'reviewer']

def record(row):
    return {c.name: getattr(row, c.name) for c in row.__table__.columns if c.name not in ['password_hash', 'artifact']}

def paginate(rows, page, page_size):
    return {'items': rows[(page-1)*page_size:page*page_size], 'total': len(rows), 'page': page, 'page_size': page_size}

@app.get('/api/health')
def health(): return {'status': 'ok', 'time': now()}

@app.post('/api/auth/register', status_code=201)
def register(body: Credentials, s: Session = Depends(db)):
    if s.scalar(select(User).where(User.email == body.email.lower())): raise HTTPException(409, 'Email already registered')
    production = os.getenv('ENVIRONMENT') == 'production'
    if production and os.getenv('ALLOW_PUBLIC_REGISTRATION', '').lower() != 'true':
        raise HTTPException(403, 'Account registration is not enabled for this workspace')
    # Public production signup always creates an analyst, even in an empty database.
    role = 'admin' if not production and not s.scalar(select(User.id).limit(1)) else 'analyst'
    user = User(email=body.email.lower(), password_hash=hasher.hash(body.password), role=role)
    s.add(user); s.commit(); audit(s, user, 'register', {})
    return {'access_token': token(user), 'token_type': 'bearer', 'user': record(user)}

@app.post('/api/auth/login')
def login(body: Credentials, s: Session = Depends(db)):
    user = s.scalar(select(User).where(User.email == body.email.lower()))
    if not user or not hasher.verify(body.password, user.password_hash): raise HTTPException(401, 'Invalid email or password')
    audit(s, user, 'login', {})
    return {'access_token': token(user), 'token_type': 'bearer', 'user': record(user)}

@app.get('/api/auth/me')
def me(user=Depends(current_user)): return record(user)

@app.get('/api/customers')
def customers(search: str = '', risk: str = '', page: int = 1, page_size: int = 20, user=Depends(current_user), s: Session = Depends(db)):
    if page < 1 or not 1 <= page_size <= 100: raise HTTPException(422, 'Invalid pagination')
    ps = {p.customer_id: p for p in latest_predictions(s)}
    query = select(Customer).where(Customer.id.contains(search))
    if risk: query = query.where(Customer.id.in_([cid for cid,p in ps.items() if p.risk == risk]))
    total = s.scalar(select(func.count()).select_from(query.subquery()))
    customers_page = s.scalars(query.order_by(Customer.id).offset((page-1)*page_size).limit(page_size)).all()
    segs = {row.customer_id: row for row in s.scalars(select(Segment).where(Segment.customer_id.in_([c.id for c in customers_page]))).all()}
    rows = []
    for c in customers_page:
        p = ps.get(c.id); seg = segs.get(c.id)
        rows.append({'customer_id': c.id, **c.data, 'source': c.source, 'consent': c.consent, 'probability': p.probability if p else None, 'risk': p.risk if p else 'Unscored', 'segment': seg.name if seg else None, 'annual_revenue_proxy': seg.value if seg else None})
    return {'items': rows, 'total':total, 'page':page, 'page_size':page_size}

@app.get('/api/customers/{cid}')
@app.get('/api/customers/{cid}/profile')
def profile(cid: str, user=Depends(current_user), s: Session = Depends(db)): return Registry(s, user).call('get_customer_profile', {'customer_id': cid})

@app.get('/api/customers/{cid}/transactions')
def transactions(cid: str, user=Depends(current_user), s: Session = Depends(db)): return Registry(s, user).call('get_customer_transactions', {'customer_id': cid, 'limit': 100})

@app.post('/api/data/demo', status_code=201)
def seed(user=Depends(roles('admin', 'analyst')), s: Session = Depends(db)):
    result = demo(s); audit(s, user, 'synthetic_demo_created', result); return result

@app.post('/api/data/upload', status_code=201)
def upload(file: UploadFile = File(...), mapping: str = Form('{}'), user=Depends(roles('admin', 'analyst')), s: Session = Depends(db)):
    raw = file.file.read(10*1024*1024+1)
    if len(raw) > 10*1024*1024: raise HTTPException(413, 'Upload exceeds 10 MB')
    try:
        columns = json.loads(mapping)
        if not isinstance(columns, dict) or not all(isinstance(k, str) and isinstance(v, str) for k,v in columns.items()): raise ValueError()
        name = (file.filename or '').lower()
        if name.endswith('.csv'): frame = pd.read_csv(io.BytesIO(raw), dtype={'customer_id': str})
        elif name.endswith('.json'):
            records = json.loads(raw)
            if not isinstance(records, list) or not all(isinstance(r, dict) for r in records): raise ValueError()
            frame = pd.DataFrame(records)
        else: raise HTTPException(415, 'Upload a CSV or JSON array of customer snapshots')
    except (ValueError, UnicodeError, pd.errors.ParserError): raise HTTPException(422, 'Invalid data file or column mapping JSON')
    result = ingest(s, frame, columns); audit(s, user, 'data_uploaded', result); return result

@app.get('/api/data/status')
def data_status(user=Depends(current_user), s: Session = Depends(db)): return {'datasets': [record(d) for d in s.scalars(select(Dataset).order_by(Dataset.created_at.desc())).all()]}

@app.get('/api/data/preview')
def preview(user=Depends(current_user), s: Session = Depends(db)): return {'items': [record(c) for c in s.scalars(select(Customer).limit(10)).all()]}

@app.post('/api/churn/train')
def training(body: DatasetInput, user=Depends(roles('admin', 'analyst')), s: Session = Depends(db)):
    result = train(s, body.dataset_id); audit(s, user, 'model_trained', {'model_version': result['model_version']}); return result

@app.post('/api/churn/predict')
def predict_one(body: CustomerInput, user=Depends(roles('admin', 'analyst')), s: Session = Depends(db)):
    result = predict(s, [body.customer_id]); audit(s, user, 'prediction_created', body.model_dump()); return record(result[0])

@app.post('/api/churn/predict/batch')
def predict_batch(body: BatchInput, user=Depends(roles('admin', 'analyst')), s: Session = Depends(db)):
    rows = predict(s, body.customer_ids); audit(s, user, 'batch_prediction', {'count': len(rows)}); return {'count': len(rows), 'items': [record(r) for r in rows]}

@app.get('/api/churn/predictions')
def predictions(page: int = 1, page_size: int = 20, user=Depends(current_user), s: Session = Depends(db)):
    if page < 1 or not 1 <= page_size <= 100: raise HTTPException(422, 'Invalid pagination')
    return paginate([record(p) for p in latest_predictions(s)], page, page_size)

@app.get('/api/churn/high-risk')
def high_risk(user=Depends(current_user), s: Session = Depends(db)): return Registry(s,user).call('get_high_risk_customers', {'limit': 100})

@app.get('/api/churn/model-performance')
def performance(user=Depends(current_user), s: Session = Depends(db)): return {'models': [record(m) for m in s.scalars(select(ModelVersion).order_by(ModelVersion.created_at.desc())).all()]}

@app.get('/api/explainability/global')
@app.get('/api/explainability/features')
def global_explanation(user=Depends(current_user), s: Session = Depends(db)):
    m = latest_model(s)
    return {'model_version': m.id, 'method': m.metrics['method'], 'features': m.metrics['global_shap'], 'distribution': m.metrics['shap_distribution'], 'permutation': m.metrics['permutation'], 'limitations': 'Attributions describe the model, not causation. Values are from held-out rows.'}

@app.get('/api/explainability/customer/{cid}')
def local_explanation(cid: str, user=Depends(current_user), s: Session = Depends(db)):
    customer(s, cid); return Registry(s,user).call('explain_customer_prediction', {'customer_id': cid})

@app.post('/api/segmentation/run')
def run_segments(user=Depends(roles('admin', 'analyst')), s: Session = Depends(db)):
    result = Registry(s,user).call('segment_customers', {}); audit(s, user, 'segmentation_run', {'count': len(result['segments'])}); return result

@app.get('/api/segmentation')
def segments(user=Depends(current_user), s: Session = Depends(db)): return {'items': [record(row) for row in s.scalars(select(Segment)).all()], 'policy': POLICY}

@app.get('/api/segmentation/{name}')
def segment_detail(name: str, user=Depends(current_user), s: Session = Depends(db)): return {'items': [record(row) for row in s.scalars(select(Segment).where(Segment.name == name)).all()]}

@app.post('/api/retention/generate')
def generate(body: CustomerInput, user=Depends(roles('admin', 'analyst')), s: Session = Depends(db)): return Registry(s,user).call('generate_retention_strategy', body.model_dump())

@app.get('/api/retention/strategies')
def strategies(user=Depends(current_user), s: Session = Depends(db)): return {'items': [record(r) for r in s.scalars(select(Strategy).order_by(Strategy.id.desc())).all()]}

@app.get('/api/retention/customer/{cid}')
def customer_strategies(cid: str, user=Depends(current_user), s: Session = Depends(db)): return {'items': [record(r) for r in s.scalars(select(Strategy).where(Strategy.customer_id == cid)).all()]}

@app.post('/api/retention/approve')
def approve(body: Approval, user=Depends(roles('admin', 'reviewer')), s: Session = Depends(db)):
    if body.kind == 'execution':
        row = s.get(Execution, body.id)
        if not row: raise HTTPException(404, 'Execution not found')
        if row.status != 'awaiting_review': raise HTTPException(409, 'Execution is not awaiting review')
        result = workflow(s,user,row.id,resume=body.approved)
    else:
        try: item_id = int(body.id)
        except ValueError: raise HTTPException(422, 'ID must be an integer')
        row = s.get(Campaign if body.kind == 'campaign' else Strategy, item_id)
        if not row: raise HTTPException(404, 'Draft not found')
        if row.status != 'draft': raise HTTPException(409, 'Only drafts can be reviewed')
        if body.kind == 'campaign' and body.approved:
            audience = s.scalars(select(Customer).join(CampaignCustomer).where(CampaignCustomer.campaign_id == row.id)).all()
            if not audience or (row.channel == 'email' and not all(c.consent for c in audience)): raise HTTPException(422, 'Email audience must have recorded marketing consent')
            row.approved_by = user.id
        row.status = 'approved' if body.approved else 'rejected'; s.commit(); result = record(row)
    audit(s,user,'human_review',body.model_dump()); return result

@app.get('/api/agents')
def agents(user=Depends(current_user)): return {'agents': [{'id': a, 'name': b, 'tools': c, 'engine': 'LangGraph typed state + SQLite checkpoints'} for a,b,c in AGENTS]}

@app.post('/api/agents/run')
def run_agents(body: CustomerInput, user=Depends(roles('admin', 'analyst')), s: Session = Depends(db)):
    result = start_workflow(s,user,body.customer_id); audit(s,user,'workflow_started',{'execution_id': result['execution_id']}); return result

@app.get('/api/agents/executions')
def executions(user=Depends(current_user), s: Session = Depends(db)): return {'items': [record(r) for r in s.scalars(select(Execution).order_by(Execution.created_at.desc())).all()]}

@app.get('/api/agents/executions/{eid}')
def execution(eid: str, user=Depends(current_user), s: Session = Depends(db)):
    row = s.get(Execution, eid)
    if not row: raise HTTPException(404, 'Execution not found')
    return {**record(row), 'tool_calls': [record(t) for t in s.scalars(select(ToolCall).where(ToolCall.execution_id == eid)).all()]}

@app.get('/api/tools')
def tools(user=Depends(current_user)): return {'tools': Registry.specs(), 'policy': POLICY}

@app.post('/api/assistant/query')
def ask(body: Question, user=Depends(current_user), s: Session = Depends(db)):
    try: return assistant(s,user,body.question,body.customer_id)
    except (httpx.HTTPError, KeyError) as exc: raise HTTPException(502, 'LLM provider unavailable or returned an invalid response; use local mode by removing provider settings') from exc

@app.get('/api/campaigns')
def campaigns(user=Depends(current_user), s: Session = Depends(db)):
    return {'items': [{**record(c), 'customer_ids': list(s.scalars(select(CampaignCustomer.customer_id).where(CampaignCustomer.campaign_id == c.id)).all())} for c in s.scalars(select(Campaign).order_by(Campaign.id.desc())).all()]}

@app.post('/api/campaigns/draft', status_code=201)
def draft(body: CampaignInput, user=Depends(roles('admin','analyst')), s: Session = Depends(db)):
    ids = set(body.customer_ids)
    for cid in ids: customer(s,cid)
    row = Campaign(name=body.name, channel=body.channel); s.add(row); s.flush()
    for cid in ids: s.add(CampaignCustomer(campaign_id=row.id, customer_id=cid))
    s.commit(); audit(s,user,'campaign_drafted',{'id':row.id}); return record(row)

@app.get('/api/campaigns/performance')
def campaign_metrics(user=Depends(current_user), s: Session = Depends(db)): return campaign_performance(s)

@app.post('/api/campaigns/{campaign_id}/outcomes', status_code=201)
def outcome(campaign_id: int, body: OutcomeInput, user=Depends(roles('admin','reviewer')), s: Session = Depends(db)):
    c = s.get(Campaign,campaign_id)
    if not c or not s.get(CampaignCustomer,(campaign_id,body.customer_id)): raise HTTPException(404, 'Customer is not in this campaign')
    if c.status != 'approved': raise HTTPException(409,'Approve the campaign before recording an external outcome')
    try:
        timestamp = pd.to_datetime(body.observed_at, utc=True)
        if timestamp > pd.Timestamp.now(tz='UTC') or timestamp < pd.to_datetime(c.created_at, utc=True): raise ValueError()
    except (ValueError, TypeError): raise HTTPException(422,'Observation must fall between campaign creation and now')
    if s.scalar(select(Outcome).where(Outcome.campaign_id == campaign_id, Outcome.customer_id == body.customer_id)): raise HTTPException(409,'An outcome is already recorded for this campaign customer')
    row = Outcome(campaign_id=campaign_id, **body.model_dump()); s.add(row); s.commit(); audit(s,user,'outcome_recorded',{'id':row.id}); return record(row)

@app.get('/api/analytics')
def analytics(user=Depends(current_user), s: Session = Depends(db)):
    cs = s.scalars(select(Customer)).all(); ps = latest_predictions(s)
    labels = [c.data['churn_label'] for c in cs if c.data.get('churn_label') is not None]
    risk = {k: sum(p.risk == k for p in ps) for k in ['Low','Medium','High']}
    dates = defaultdict(list)
    for p in ps: dates[p.created_at[:10]].append(p.probability)
    return {'total_customers': len(cs), 'observed_active_customers': sum(v == 0 for v in labels), 'observed_churned': sum(v == 1 for v in labels), 'labeled_customers': len(labels), 'observed_churn_rate': sum(labels)/len(labels) if labels else None, 'average_probability': float(np.mean([p.probability for p in ps])) if ps else None, 'predicted_high_risk': risk['High'], 'scored_customers': len(ps), 'high_value_at_risk': sum(p.risk == 'High' and float(customer(s,p.customer_id).data.get('total_spend') or 0) >= 2000 for p in ps), 'strategies': s.scalar(select(func.count()).select_from(Strategy)), 'risk_distribution': [{'name':k,'value':v} for k,v in risk.items()], 'prediction_trend': [{'date':d,'probability':float(np.mean(v))} for d,v in sorted(dates.items())], 'actual_churn_trend': [], 'trend_limitation': 'No historical observed churn series is supplied; snapshots are not a trend.', 'sources': sorted(set(c.source for c in cs)), 'total_spend': sum(float(c.data.get('total_spend') or 0) for c in cs), 'campaigns': campaign_performance(s), 'risk_thresholds': (s.get(Setting,'risk').value if s.get(Setting,'risk') else {'medium':.35,'high':.65})}

@app.post('/api/reports/generate', status_code=201)
def report_generate(body: ReportInput, user=Depends(current_user), s: Session = Depends(db)):
    data = analytics(user,s)
    m = s.scalar(select(ModelVersion).order_by(ModelVersion.created_at.desc()))
    row = Report(title=body.title, content={'analytics':data, 'model':record(m) if m else None, 'generated_at':now(), 'limitations': 'Predictions are estimates. Actions are recommendations. Campaign outcomes require recorded observations; no causal improvement is claimed.'})
    s.add(row); s.commit(); audit(s,user,'report_generated',{'id':row.id}); return record(row)

@app.get('/api/reports')
def reports(user=Depends(current_user), s: Session = Depends(db)): return {'items':[record(r) for r in s.scalars(select(Report).order_by(Report.id.desc())).all()]}

@app.get('/api/reports/{report_id}/export')
def report_export(report_id: int, format: Literal['json','csv']='json', user=Depends(current_user), s: Session = Depends(db)):
    row = s.get(Report,report_id)
    if not row: raise HTTPException(404,'Report not found')
    if format == 'csv':
        flat = pd.json_normalize(row.content, sep='.')
        content = flat.to_csv(index=False); media = 'text/csv'
    else: content = json.dumps(record(row),indent=2); media = 'application/json'
    return Response(content, media_type=media, headers={'Content-Disposition':f'attachment; filename="retainiq-report-{report_id}.{format}"'})

@app.get('/api/settings')
def settings(user=Depends(current_user), s: Session = Depends(db)):
    return {'risk': s.get(Setting,'risk').value if s.get(Setting,'risk') else {'medium':.35,'high':.65}, 'llm': {'mode':'provider' if os.getenv('LLM_API_KEY') and os.getenv('LLM_BASE_URL') else 'local tool router', 'model':os.getenv('LLM_MODEL'), 'configured':bool(os.getenv('LLM_API_KEY')), 'note':'Provider credentials are configured through environment variables, never the browser.'}, 'policy':POLICY}

@app.put('/api/settings/risk')
def set_risk(body: RiskSettings, user=Depends(roles('admin')), s: Session = Depends(db)):
    if body.medium >= body.high: raise HTTPException(422,'Medium threshold must be below high threshold')
    row = s.get(Setting,'risk')
    if row: row.value = body.model_dump()
    else: s.add(Setting(key='risk',value=body.model_dump()))
    s.commit(); audit(s,user,'risk_settings_changed',body.model_dump()); return {'risk':body.model_dump(),'note':'Run batch prediction to apply these thresholds to new prediction records.'}

@app.get('/api/model/drift')
def drift(user=Depends(current_user), s: Session = Depends(db)):
    m = latest_model(s)
    rows = pd.DataFrame([c.data for c in s.scalars(select(Customer)).all()])
    result=[]
    for feature, stats in m.metrics['baseline_features'].items():
        mean = float(pd.to_numeric(rows[feature],errors='coerce').mean())
        if stats['mean'] is None or stats['std'] is None or not np.isfinite(mean):
            result.append({'feature':feature,'standardized_mean_shift':None,'flag':False,'note':'Insufficient nonmissing observations'})
            continue
        shift = abs(mean-stats['mean']) / max(stats['std'],1e-6)
        result.append({'feature':feature,'standardized_mean_shift':shift,'flag':shift>1})
    return {'features':result,'limitation':'Population mean shift diagnostic, not proof of drift or degraded prediction quality. Compare delayed observed labels separately.'}

@app.get('/api/users')
def users(user=Depends(roles('admin')), s: Session = Depends(db)): return {'items':[record(u) for u in s.scalars(select(User)).all()]}

@app.put('/api/users/{uid}/role')
def user_role(uid: int, body: RoleInput, user=Depends(roles('admin')), s: Session = Depends(db)):
    row = s.get(User,uid)
    if not row: raise HTTPException(404,'User not found')
    if row.id == user.id: raise HTTPException(422,'An administrator cannot remove their own role')
    row.role=body.role; s.commit(); audit(s,user,'role_changed',{'user_id':uid,'role':body.role}); return record(row)

@app.get('/api/audit')
def audits(user=Depends(roles('admin','reviewer')), s: Session = Depends(db)): return {'items':[record(a) for a in s.scalars(select(Audit).order_by(Audit.id.desc()).limit(200)).all()]}

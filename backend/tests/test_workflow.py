from datetime import datetime, timezone
from fastapi.testclient import TestClient
from app.main import app
from app.core import SessionLocal
from app.models import User
from app.ml import Features
import pandas as pd
import numpy as np
import pytest

@pytest.fixture(scope='module')
def client():
    with TestClient(app) as c:
        result=c.post('/api/auth/register',json={'email':'admin@example.com','password':'StrongPassword42!'})
        assert result.status_code==201, result.text
        c.headers['Authorization']='Bearer '+result.json()['access_token']
        yield c

def test_auth_and_roles(client):
    assert client.get('/api/auth/me').json()['role']=='admin'
    assert client.post('/api/auth/login',json={'email':'admin@example.com','password':'wrongPassword'}).status_code==401
    assert TestClient(app).get('/api/customers').status_code==401
    r=client.post('/api/auth/register',json={'email':'analyst@example.com','password':'StrongPassword42!'})
    other=TestClient(app); other.headers['Authorization']='Bearer '+r.json()['access_token']
    assert other.get('/api/users').status_code==403
    assert other.post('/api/retention/approve',json={'kind':'campaign','id':'1','approved':True}).status_code==403

def test_upload_validation(client):
    invalid='customer_id,total_orders,total_spend,days_since_last_purchase\nA,3,-4,30'
    assert client.post('/api/data/upload',files={'file':('bad.csv',invalid,'text/csv')}).status_code==422
    valid='id,total_orders,total_spend,days_since_last_purchase,gender\nIM001,3,40,30,F\nIM001,3,40,30,F'
    r=client.post('/api/data/upload',files={'file':('good.csv',valid,'text/csv')},data={'mapping':'{"id":"customer_id"}'})
    assert r.status_code==201,r.text
    assert r.json()['duplicates_removed']==1
    assert r.json()['ignored_columns']==['gender']
    assert client.get('/api/customers/IM001/transactions').json()['transactions']==[]
    assert client.post('/api/data/upload',files={'file':('good.csv',valid,'text/csv')},data={'mapping':'{"id":"customer_id"}'}).status_code==409
    assert client.post('/api/data/upload',files={'file':('bad.json','{"not":"array"}','application/json')}).status_code==422

def test_features_exclude_target():
    out=Features().transform(pd.DataFrame([{'total_orders':2,'total_spend':100,'churn_label':1,'gender':'X'}]))
    assert out.average_order_value.iloc[0]==50
    assert 'churn_label' not in out and 'gender' not in out

def test_complete_workflow(client):
    result=client.post('/api/data/demo'); assert result.status_code==201,result.text
    dataset=result.json()['dataset_id']
    trained=client.post('/api/churn/train',json={'dataset_id':dataset}); assert trained.status_code==200,trained.text
    details=trained.json()
    assert len(details['validation'])>=4
    assert sum(details['sizes'].values())==360
    assert 0 <= details['test']['pr_auc'] <= 1
    assert sum(sum(r) for r in details['test']['confusion_matrix'])==details['sizes']['test']
    scored=client.post('/api/churn/predict/batch',json={}); assert scored.status_code==200,scored.text
    assert scored.json()['count']==360
    cid=scored.json()['items'][0]['customer_id']
    explanation=client.get('/api/explainability/customer/'+cid).json()
    assert explanation['method'].startswith('SHAP') and explanation['factors']
    assert all(np.isfinite(f['contribution']) for f in explanation['factors'])
    global_result=client.get('/api/explainability/global'); assert global_result.status_code==200
    assert len(global_result.json()['distribution'])>10
    assert client.post('/api/segmentation/run').status_code==200
    started=client.post('/api/agents/run',json={'customer_id':cid}); assert started.status_code==200,started.text
    assert started.json()['status']=='awaiting_review'
    execution_id=started.json()['execution_id']
    logs=client.get('/api/agents/executions/'+execution_id).json()
    assert len(logs['tool_calls'])>=12
    approved=client.post('/api/retention/approve',json={'kind':'execution','id':execution_id,'approved':True})
    assert approved.status_code==200,approved.text
    assert approved.json()['status']=='approved'
    assert client.post('/api/assistant/query',json={'question':'Why is this customer at risk?','customer_id':cid}).json()['evidence'][0]['tool']=='explain_customer_prediction'
    assert client.post('/api/assistant/query',json={'question':'generate retention strategy','customer_id':cid}).status_code==200
    # Campaign approval enforces actual recorded consent.
    rows=client.get('/api/customers',params={'page_size':100}).json()['items']
    consented=next(c['customer_id'] for c in rows if c['consent'])
    blocked=next(c['customer_id'] for c in rows if not c['consent'])
    draft=client.post('/api/campaigns/draft',json={'name':'Test consent gate','customer_ids':[blocked]}).json()
    assert client.post('/api/retention/approve',json={'kind':'campaign','id':str(draft['id']),'approved':True}).status_code==422
    good=client.post('/api/campaigns/draft',json={'name':'Reviewed customer outreach','customer_ids':[consented]}).json()
    assert client.post('/api/retention/approve',json={'kind':'campaign','id':str(good['id']),'approved':True}).status_code==200
    body={'customer_id':consented,'retained':True,'cost':4.5,'evidence':'External purchase receipt, independently observed.','observed_at':datetime.now(timezone.utc).isoformat()}
    assert client.post(f'/api/campaigns/{good["id"]}/outcomes',json=body).status_code==201
    assert client.post(f'/api/campaigns/{good["id"]}/outcomes',json=body).status_code==409
    perf=client.get('/api/campaigns/performance').json()
    assert perf['estimated_causal_impact'] is None
    assert sum(c['observed_retained'] for c in perf['campaigns'])==1
    report=client.post('/api/reports/generate',json={}); assert report.status_code==201
    assert client.get(f'/api/reports/{report.json()["id"]}/export?format=csv').status_code==200
    assert client.get('/api/analytics').json()['scored_customers']==360
    assert client.get('/api/model/drift').status_code==200
    assert client.put('/api/settings/risk',json={'medium':.9,'high':.5}).status_code==422
    assert client.put('/api/settings/risk',json={'medium':.3,'high':.6}).status_code==200
    assert len(client.get('/api/audit').json()['items'])>10

def test_sparse_optional_features(client):
    rows=[{'customer_id':f'SPARSE-{i}', 'total_orders':i%15+1,'total_spend':(i%15+1)*40,'days_since_last_purchase':i+1,'churn_label':int(i%3==0)} for i in range(90)]
    import json
    r=client.post('/api/data/upload',files={'file':('sparse.json',json.dumps(rows),'application/json')})
    assert r.status_code==201,r.text
    trained=client.post('/api/churn/train',json={'dataset_id':r.json()['dataset_id']})
    assert trained.status_code==200,trained.text
    assert trained.json()['baseline_features']['email_engagement']['mean'] is None
    scored=client.post('/api/churn/predict',json={'customer_id':'SPARSE-1'})
    assert scored.status_code==200,scored.text
    assert 0<=scored.json()['probability']<=1
    assert client.get('/api/model/drift').status_code==200

def test_target_window_validation(client):
    import json
    row={'customer_id':'BAD-TIME','total_orders':4,'total_spend':80,'days_since_last_purchase':30,'churn_label':1,'snapshot_date':'2026-01-05','label_observed_at':'2026-01-01'}
    r=client.post('/api/data/upload',files={'file':('temporal.json',json.dumps([row]),'application/json')})
    assert r.status_code==422

def test_tool_permission_and_logging(client):
    from app.intelligence import Registry
    from app.models import ToolCall
    from sqlalchemy import select
    from fastapi import HTTPException
    with SessionLocal() as s:
        user=s.scalar(select(User).where(User.email=='analyst@example.com'))
        user.role='reviewer';s.commit()
        with pytest.raises(HTTPException) as exc:
            Registry(s,user).call('generate_retention_strategy',{'customer_id':'SPARSE-1'})
        assert exc.value.status_code==403
        row=s.scalar(select(ToolCall).order_by(ToolCall.id.desc()))
        assert row.result['status']=='error'

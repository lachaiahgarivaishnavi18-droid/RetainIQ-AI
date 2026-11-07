import json
import uuid
from datetime import date, timedelta
import numpy as np
import pandas as pd
from fastapi import HTTPException
from sqlalchemy import select
from .models import Customer, Dataset, Transaction

NUMERIC = ['total_orders', 'total_spend', 'days_since_last_purchase', 'returns_count', 'complaints_count', 'website_visits', 'email_engagement', 'discount_usage', 'loyalty_points', 'customer_tenure_days']
CATEGORICAL = ['membership_status', 'region']
ALLOWED = set(NUMERIC + CATEGORICAL + ['customer_id', 'churn_label', 'marketing_consent', 'snapshot_date', 'label_observed_at'])

def clean(frame: pd.DataFrame, mapping: dict):
    frame = frame.rename(columns=mapping)
    if frame.columns.duplicated().any():
        raise HTTPException(422, 'Mapping creates duplicate columns')
    required = {'customer_id', 'total_orders', 'total_spend', 'days_since_last_purchase'}
    if required - set(frame.columns):
        raise HTTPException(422, f'Missing columns: {sorted(required - set(frame.columns))}')
    if len(frame) == 0 or len(frame) > 20000:
        raise HTTPException(422, 'Provide 1–20,000 customer snapshot rows')
    ignored = sorted(set(frame.columns) - ALLOWED)
    frame = frame[[c for c in frame.columns if c in ALLOWED]].copy()
    if frame.customer_id.isna().any():
        raise HTTPException(422, 'customer_id cannot be missing')
    frame['customer_id'] = frame.customer_id.astype(str).str.strip()
    if (~frame.customer_id.str.fullmatch(r'[A-Za-z0-9_-]{1,100}')).any():
        raise HTTPException(422, 'Customer IDs must use 1–100 letters, digits, underscores or hyphens')
    duplicates = int(frame.customer_id.duplicated().sum())
    frame = frame.drop_duplicates('customer_id', keep='first')
    missing, outliers = {}, {}
    for col in NUMERIC:
        if col not in frame:
            frame[col] = np.nan
        original = frame[col]
        vals = pd.to_numeric(original, errors='coerce')
        if (original.notna() & vals.isna()).any() or np.isinf(vals).any() or (vals.dropna() < 0).any():
            raise HTTPException(422, f'{col} must contain finite, nonnegative numbers or blanks')
        if col in ['email_engagement', 'discount_usage'] and (vals.dropna() > 1).any():
            raise HTTPException(422, f'{col} must be between 0 and 1')
        missing[col] = int(vals.isna().sum())
        q1, q3 = vals.quantile([.25, .75])
        outliers[col] = int(((vals < q1 - 1.5*(q3-q1)) | (vals > q3 + 1.5*(q3-q1))).sum())
        frame[col] = vals
    for col in CATEGORICAL:
        if col not in frame:
            frame[col] = 'Unknown'
        frame[col] = frame[col].fillna('Unknown').astype(str).str.slice(0, 100)
    if 'churn_label' in frame:
        labels = pd.to_numeric(frame.churn_label, errors='coerce')
        if (frame.churn_label.notna() & labels.isna()).any() or not labels.dropna().isin([0, 1]).all():
            raise HTTPException(422, 'churn_label must be 0, 1, or blank')
        frame['churn_label'] = labels
    for col in ['snapshot_date', 'label_observed_at']:
        if col in frame:
            dates = pd.to_datetime(frame[col], errors='coerce', utc=True)
            if dates.isna().any():
                raise HTTPException(422, f'Every {col} must be a valid date')
            frame[col] = dates.dt.strftime('%Y-%m-%d')
    if 'snapshot_date' in frame and 'label_observed_at' in frame:
        if (frame.label_observed_at <= frame.snapshot_date).any():
            raise HTTPException(422, 'Labels must be observed after the feature snapshot')
    if 'marketing_consent' in frame:
        def consent(v):
            if pd.isna(v): return False
            if str(v).lower() in ['true', '1', 'yes']: return True
            if str(v).lower() in ['false', '0', 'no']: return False
            raise HTTPException(422, 'marketing_consent must be true/false, yes/no, or 1/0')
        frame['marketing_consent'] = frame.marketing_consent.map(consent)
    else:
        frame['marketing_consent'] = False
    return frame, {'rows': len(frame), 'duplicates_removed': duplicates, 'missing_values': missing, 'outliers_flagged': outliers, 'ignored_columns': ignored, 'note': 'Outliers are flagged, not silently removed. Median imputation is fit on training rows only. Labels must describe a future observation window; snapshot semantics require data-owner review.'}

def ingest(session, frame, mapping=None, source='uploaded'):
    frame, summary = clean(frame, mapping or {})
    if session.scalar(select(Customer.id).where(Customer.id.in_(frame.customer_id.tolist())).limit(1)):
        raise HTTPException(409, 'Customer IDs already exist. Use a new snapshot ID or a fresh database; existing evidence is preserved.')
    dataset_id = uuid.uuid4().hex
    session.add(Dataset(id=dataset_id, source=source, summary=summary))
    session.flush()
    for row in json.loads(frame.to_json(orient='records')):
        session.add(Customer(id=row['customer_id'], data=row, source=source, dataset_id=dataset_id, consent=row['marketing_consent']))
    session.commit()
    return {'dataset_id': dataset_id, 'source': source, **summary}

def demo(session, count=360):
    rng = np.random.default_rng(42)
    prefix = 'DEMO-' + uuid.uuid4().hex[:4] + '-'
    recency = rng.integers(1, 200, count)
    orders = rng.integers(1, 45, count)
    complaints = rng.poisson(.65, count)
    engagement = rng.beta(2, 2, count)
    score = -2.1 + recency / 65 + complaints * .55 - engagement * 1.5 - orders / 40
    labels = rng.binomial(1, 1 / (1 + np.exp(-score)))
    rows = pd.DataFrame({'customer_id': [prefix + str(i+1).zfill(4) for i in range(count)], 'total_orders': orders, 'total_spend': np.round(orders * rng.uniform(25, 160, count), 2), 'days_since_last_purchase': recency, 'returns_count': rng.poisson(1, count), 'complaints_count': complaints, 'website_visits': rng.integers(0, 40, count), 'email_engagement': engagement, 'discount_usage': rng.uniform(0, 1, count), 'loyalty_points': rng.integers(0, 2500, count), 'customer_tenure_days': rng.integers(210, 1800, count), 'membership_status': rng.choice(['Standard', 'Silver', 'Gold'], count), 'region': rng.choice(['North', 'South', 'East', 'West'], count), 'churn_label': labels, 'marketing_consent': rng.random(count) > .2})
    result = ingest(session, rows, source='synthetic demo')
    # Demonstration transaction history reconciles exactly to each snapshot's orders/spend.
    for row in rows.to_dict('records'):
        n = int(row['total_orders'])
        cents = int(round(row['total_spend'] * 100))
        for j in range(n):
            when = date.today() - timedelta(days=int(row['days_since_last_purchase']) + j * 20)
            session.add(Transaction(customer_id=row['customer_id'], purchased_at=when.isoformat(), amount=(cents // n + (1 if j < cents % n else 0)) / 100, category=['Home', 'Beauty', 'Apparel'][j % 3]))
    session.commit()
    return result

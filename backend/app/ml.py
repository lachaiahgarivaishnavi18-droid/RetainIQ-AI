import uuid
from functools import lru_cache
import joblib
import numpy as np
import pandas as pd
import shap
from fastapi import HTTPException
from sqlalchemy import select
from sklearn.base import BaseEstimator, TransformerMixin
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.impute import SimpleImputer
from sklearn.inspection import permutation_importance
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score, roc_auc_score, average_precision_score, confusion_matrix, brier_score_loss
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sklearn.tree import DecisionTreeClassifier
from .core import RUNTIME
from .data import NUMERIC, CATEGORICAL
from .models import Customer, ModelVersion, Prediction, Setting

DERIVED = ['average_order_value', 'return_ratio', 'complaint_frequency', 'engagement_score', 'average_purchase_interval']

class Features(BaseEstimator, TransformerMixin):
    def fit(self, X, y=None): return self
    def transform(self, X):
        out = X.reindex(columns=NUMERIC + CATEGORICAL).copy()
        for c in NUMERIC: out[c] = pd.to_numeric(out[c], errors='coerce')
        orders = out.total_orders.clip(lower=1)
        out['average_order_value'] = out.total_spend / orders
        out['return_ratio'] = out.returns_count / orders
        out['complaint_frequency'] = out.complaints_count / orders
        out['engagement_score'] = .6 * out.email_engagement + .4 * (out.website_visits / 40).clip(upper=1)
        out['average_purchase_interval'] = out.customer_tenure_days / orders
        for c in CATEGORICAL: out[c] = out[c].fillna('Unknown')
        return out

def metrics(y, p):
    pred = p >= .5
    tn, fp, fn, tp = confusion_matrix(y, pred, labels=[0, 1]).ravel()
    return {'accuracy': float(accuracy_score(y, pred)), 'precision': float(precision_score(y, pred, zero_division=0)), 'recall': float(recall_score(y, pred, zero_division=0)), 'f1': float(f1_score(y, pred, zero_division=0)), 'roc_auc': float(roc_auc_score(y, p)), 'pr_auc': float(average_precision_score(y, p)), 'specificity': float(tn / max(tn + fp, 1)), 'brier_score': float(brier_score_loss(y, p)), 'confusion_matrix': [[int(tn), int(fp)], [int(fn), int(tp)]]}

def train(session, dataset_id):
    customers = session.scalars(select(Customer).where(Customer.dataset_id == dataset_id)).all()
    frame = pd.DataFrame([c.data for c in customers])
    if 'churn_label' not in frame:
        raise HTTPException(422, 'Training requires observed churn_label values')
    frame = frame.dropna(subset=['churn_label'])
    if len(frame) < 60 or frame.churn_label.nunique() != 2 or frame.churn_label.value_counts().min() < 12:
        raise HTTPException(422, 'Training requires at least 60 labeled rows and 12 per class')
    y = frame.churn_label.astype(int)
    X = frame.reindex(columns=NUMERIC + CATEGORICAL)
    split = 'stratified 60/20/20 (snapshot timing not supplied; future-window label semantics must be verified)'
    if 'snapshot_date' in frame and frame.snapshot_date.nunique() >= 5:
        ordered = frame.sort_values('snapshot_date').index
        a, b = frame.loc[ordered[int(len(frame)*.6)], 'snapshot_date'], frame.loc[ordered[int(len(frame)*.8)], 'snapshot_date']
        tr, va, te = frame.index[frame.snapshot_date < a], frame.index[(frame.snapshot_date >= a) & (frame.snapshot_date < b)], frame.index[frame.snapshot_date >= b]
        if 'label_observed_at' not in frame:
            raise HTTPException(422, 'Temporal training requires label_observed_at to purge overlapping future labels')
        tr = tr[frame.loc[tr, 'label_observed_at'] < a]
        va = va[frame.loc[va, 'label_observed_at'] < b]
        split = 'chronological 60/20/20 boundaries with label-window purging'
    else:
        tr, rest = train_test_split(frame.index, test_size=.4, stratify=y, random_state=42)
        va, te = train_test_split(rest, test_size=.5, stratify=y.loc[rest], random_state=42)
    if any(len(ix) < 8 or y.loc[ix].nunique() != 2 for ix in [tr, va, te]):
        raise HTTPException(422, 'Each split must contain both classes and at least eight rows')
    candidates = {'Logistic Regression': LogisticRegression(max_iter=1000, class_weight='balanced'), 'Decision Tree': DecisionTreeClassifier(max_depth=5, min_samples_leaf=5, class_weight='balanced', random_state=42), 'Random Forest': RandomForestClassifier(n_estimators=90, max_depth=7, min_samples_leaf=3, class_weight='balanced', random_state=42, n_jobs=1), 'Gradient Boosting': GradientBoostingClassifier(n_estimators=70, max_depth=2, random_state=42)}
    optional = 'not installed'
    try:
        from xgboost import XGBClassifier
        candidates['XGBoost'] = XGBClassifier(n_estimators=70, max_depth=3, random_state=42, n_jobs=1, scale_pos_weight=float((y.loc[tr] == 0).sum() / (y.loc[tr] == 1).sum()))
        optional = 'included'
    except ImportError: pass
    scores, pipelines = {}, {}
    for name, estimator in candidates.items():
        prep = ColumnTransformer([('num', Pipeline([('impute', SimpleImputer(strategy='median', keep_empty_features=True)), ('scale', StandardScaler())]), NUMERIC + DERIVED), ('cat', OneHotEncoder(handle_unknown='ignore', sparse_output=False), CATEGORICAL)], verbose_feature_names_out=False)
        pipe = Pipeline([('features', Features()), ('preprocess', prep), ('classifier', estimator)])
        pipe.fit(X.loc[tr], y.loc[tr])
        scores[name] = metrics(y.loc[va], pipe.predict_proba(X.loc[va])[:, 1])
        pipelines[name] = pipe
    selected = max(scores, key=lambda name: scores[name]['pr_auc'])
    pipe = pipelines[selected]
    test = metrics(y.loc[te], pipe.predict_proba(X.loc[te])[:, 1])
    version = uuid.uuid4().hex[:12]
    background = pipe[:-1].transform(X.loc[tr].head(40))
    names = pipe.named_steps['preprocess'].get_feature_names_out().tolist()
    artifact = RUNTIME / f'{version}.joblib'
    joblib.dump({'pipeline': pipe, 'background': background, 'feature_names': names}, artifact)
    perm = permutation_importance(pipe, X.loc[te], y.loc[te], n_repeats=3, random_state=42, scoring='average_precision')
    values = explain_values({'pipeline': pipe, 'background': background}, X.loc[te].head(80))
    global_importance = sorted([{'feature': name, 'importance': float(np.abs(values[:, i]).mean())} for i, name in enumerate(names)], key=lambda r: r['importance'], reverse=True)
    baseline = {}
    for c in NUMERIC:
        vals = pd.to_numeric(X.loc[tr, c]).dropna()
        baseline[c] = {'mean': float(vals.mean()) if len(vals) else None, 'std': float(vals.std()) if len(vals) > 1 else None}
    details = {'validation': scores, 'test': test, 'selected_by': 'validation PR-AUC', 'split': split, 'sizes': {'train': len(tr), 'validation': len(va), 'test': len(te)}, 'class_balance_train': {str(k): int(v) for k, v in y.loc[tr].value_counts().items()}, 'global_shap': global_importance, 'shap_distribution': [{'feature': names[i], 'values': values[:, i].tolist()} for i in range(len(names))], 'permutation': [{'feature': c, 'importance': float(v)} for c, v in zip(X.columns, perm.importances_mean)], 'xgboost': optional, 'method': method(pipe), 'baseline_features': baseline, 'limitations': 'Associations are not causal. Synthetic demo scores do not establish real-world performance. Recall measures captured churners; precision measures how many flagged customers churn. Tune the trade-off using contact capacity and costs. Test metrics use threshold 0.5; operational risk bands are separate business settings.'}
    session.add(ModelVersion(id=version, name=selected, dataset_id=dataset_id, artifact=str(artifact), metrics=details))
    session.commit()
    return {'model_version': version, 'selected_model': selected, **details}

def latest_model(session):
    model = session.scalar(select(ModelVersion).order_by(ModelVersion.created_at.desc()))
    if not model: raise HTTPException(409, 'Train a model first')
    return model

@lru_cache(maxsize=4)
def load(path): return joblib.load(path)

def method(pipe):
    return 'SHAP LinearExplainer (log-odds)' if isinstance(pipe[-1], LogisticRegression) else 'SHAP TreeExplainer (raw model output; Random Forest uses probability)'

def explain_values(bundle, frame):
    pipe = bundle['pipeline']
    transformed = pipe[:-1].transform(frame)
    estimator = pipe[-1]
    explainer = shap.LinearExplainer(estimator, bundle['background']) if isinstance(estimator, LogisticRegression) else shap.TreeExplainer(estimator)
    result = np.asarray(explainer.shap_values(transformed))
    if result.ndim == 3: result = result[:, :, 1]
    return result

def predict(session, ids=None):
    model = latest_model(session)
    query = select(Customer).where(Customer.dataset_id == model.dataset_id)
    if ids: query = query.where(Customer.id.in_(ids))
    customers = session.scalars(query).all()
    if not customers: raise HTTPException(404, 'No customers in the trained dataset match the request')
    if ids and set(ids) != {c.id for c in customers}: raise HTTPException(422, 'Every requested customer must belong to the trained dataset')
    frame = pd.DataFrame([c.data for c in customers])
    bundle = load(model.artifact)
    pipe = bundle['pipeline']
    probabilities = pipe.predict_proba(frame)[:, 1]
    sv = explain_values(bundle, frame)
    thresholds = session.get(Setting, 'risk')
    thresholds = thresholds.value if thresholds else {'medium': .35, 'high': .65}
    output = []
    for i, c in enumerate(customers):
        p = float(probabilities[i])
        factors = sorted([{'feature': f, 'contribution': float(sv[i, j]), 'direction': 'increases risk' if sv[i, j] > 0 else 'reduces risk'} for j, f in enumerate(bundle['feature_names'])], key=lambda f: abs(f['contribution']), reverse=True)
        explanation = {'method': method(pipe), 'factors': factors, 'model_version': model.id, 'limitations': 'Feature attributions explain this model, not causality.'}
        row = Prediction(customer_id=c.id, model_id=model.id, probability=p, risk='High' if p >= thresholds['high'] else 'Medium' if p >= thresholds['medium'] else 'Low', explanation=explanation)
        session.add(row)
        output.append(row)
    session.commit()
    return output

def latest_predictions(session):
    model = session.scalar(select(ModelVersion).order_by(ModelVersion.created_at.desc()))
    if not model: return []
    rows = session.scalars(select(Prediction).where(Prediction.model_id == model.id).order_by(Prediction.id.desc())).all()
    unique = {}
    for row in rows: unique.setdefault(row.customer_id, row)
    return list(unique.values())

def customer_prediction(session, cid):
    row = next((p for p in latest_predictions(session) if p.customer_id == cid), None)
    if not row: row = predict(session, [cid])[0]
    return row

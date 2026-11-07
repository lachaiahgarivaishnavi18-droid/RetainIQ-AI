from sqlalchemy import String, Integer, Float, Boolean, ForeignKey, JSON, Text
from sqlalchemy.orm import Mapped, mapped_column
from .core import Base, now

class Stamp:
    created_at: Mapped[str] = mapped_column(String, default=now)
    updated_at: Mapped[str] = mapped_column(String, default=now, onupdate=now)

class User(Stamp, Base):
    __tablename__ = 'users'
    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(200), unique=True)
    password_hash: Mapped[str] = mapped_column(Text)
    role: Mapped[str] = mapped_column(String, default='analyst')

class Customer(Stamp, Base):
    __tablename__ = 'customers'
    id: Mapped[str] = mapped_column(String(100), primary_key=True)
    data: Mapped[dict] = mapped_column(JSON)
    source: Mapped[str] = mapped_column(String, index=True)
    dataset_id: Mapped[str] = mapped_column(String, index=True)
    consent: Mapped[bool] = mapped_column(Boolean, default=False)

class Transaction(Stamp, Base):
    __tablename__ = 'transactions'
    id: Mapped[int] = mapped_column(primary_key=True)
    customer_id: Mapped[str] = mapped_column(ForeignKey('customers.id'), index=True)
    purchased_at: Mapped[str] = mapped_column(String)
    amount: Mapped[float] = mapped_column(Float)
    category: Mapped[str] = mapped_column(String)

class Dataset(Stamp, Base):
    __tablename__ = 'datasets'
    id: Mapped[str] = mapped_column(String, primary_key=True)
    source: Mapped[str] = mapped_column(String)
    summary: Mapped[dict] = mapped_column(JSON)

class ModelVersion(Stamp, Base):
    __tablename__ = 'ml_models'
    id: Mapped[str] = mapped_column(String, primary_key=True)
    dataset_id: Mapped[str] = mapped_column(ForeignKey('datasets.id'))
    name: Mapped[str] = mapped_column(String)
    artifact: Mapped[str] = mapped_column(String)
    metrics: Mapped[dict] = mapped_column(JSON)

class Prediction(Stamp, Base):
    __tablename__ = 'churn_predictions'
    id: Mapped[int] = mapped_column(primary_key=True)
    customer_id: Mapped[str] = mapped_column(ForeignKey('customers.id'), index=True)
    model_id: Mapped[str] = mapped_column(ForeignKey('ml_models.id'), index=True)
    probability: Mapped[float] = mapped_column(Float)
    risk: Mapped[str] = mapped_column(String)
    explanation: Mapped[dict] = mapped_column(JSON)

class Segment(Stamp, Base):
    __tablename__ = 'customer_segments'
    customer_id: Mapped[str] = mapped_column(ForeignKey('customers.id'), primary_key=True)
    name: Mapped[str] = mapped_column(String)
    value: Mapped[float] = mapped_column(Float)
    metrics: Mapped[dict] = mapped_column(JSON)

class Strategy(Stamp, Base):
    __tablename__ = 'retention_strategies'
    id: Mapped[int] = mapped_column(primary_key=True)
    customer_id: Mapped[str] = mapped_column(ForeignKey('customers.id'), index=True)
    prediction_id: Mapped[int] = mapped_column(ForeignKey('churn_predictions.id'))
    status: Mapped[str] = mapped_column(String, default='draft')
    content: Mapped[dict] = mapped_column(JSON)

class Campaign(Stamp, Base):
    __tablename__ = 'retention_campaigns'
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String)
    status: Mapped[str] = mapped_column(String, default='draft')
    channel: Mapped[str] = mapped_column(String)
    approved_by: Mapped[int | None] = mapped_column(ForeignKey('users.id'), nullable=True)

class CampaignCustomer(Base):
    __tablename__ = 'campaign_customers'
    campaign_id: Mapped[int] = mapped_column(ForeignKey('retention_campaigns.id'), primary_key=True)
    customer_id: Mapped[str] = mapped_column(ForeignKey('customers.id'), primary_key=True)

class Outcome(Stamp, Base):
    __tablename__ = 'campaign_outcomes'
    id: Mapped[int] = mapped_column(primary_key=True)
    campaign_id: Mapped[int] = mapped_column(ForeignKey('retention_campaigns.id'), index=True)
    customer_id: Mapped[str] = mapped_column(ForeignKey('customers.id'))
    retained: Mapped[bool] = mapped_column(Boolean)
    cost: Mapped[float] = mapped_column(Float)
    evidence: Mapped[str] = mapped_column(Text)
    observed_at: Mapped[str] = mapped_column(String)

class Execution(Stamp, Base):
    __tablename__ = 'agent_executions'
    id: Mapped[str] = mapped_column(String, primary_key=True)
    customer_id: Mapped[str] = mapped_column(ForeignKey('customers.id'))
    status: Mapped[str] = mapped_column(String)
    output: Mapped[dict] = mapped_column(JSON, default=dict)

class ToolCall(Stamp, Base):
    __tablename__ = 'agent_tool_calls'
    id: Mapped[int] = mapped_column(primary_key=True)
    execution_id: Mapped[str | None] = mapped_column(ForeignKey('agent_executions.id'), nullable=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id'))
    name: Mapped[str] = mapped_column(String)
    arguments: Mapped[dict] = mapped_column(JSON)
    result: Mapped[dict] = mapped_column(JSON)

class Audit(Stamp, Base):
    __tablename__ = 'audit_logs'
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey('users.id'), nullable=True)
    action: Mapped[str] = mapped_column(String)
    details: Mapped[dict] = mapped_column(JSON)

class Report(Stamp, Base):
    __tablename__ = 'reports'
    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String)
    content: Mapped[dict] = mapped_column(JSON)

class Setting(Base):
    __tablename__ = 'settings'
    key: Mapped[str] = mapped_column(String, primary_key=True)
    value: Mapped[dict] = mapped_column(JSON)

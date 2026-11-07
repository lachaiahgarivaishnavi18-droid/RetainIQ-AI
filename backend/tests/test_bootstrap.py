from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from app.core import Base, hasher
from app.models import User
from app.admin import bootstrap_admin

def test_provision_first_admin_without_overwriting_existing_account(monkeypatch):
    engine = create_engine('sqlite://')
    Base.metadata.create_all(engine)
    monkeypatch.setenv('BOOTSTRAP_ADMIN_EMAIL','demo@retainiq.local')
    monkeypatch.setenv('BOOTSTRAP_ADMIN_PASSWORD','ExampleTestPassword42!')
    with Session(engine) as session:
        bootstrap_admin(session)
        user = session.scalar(select(User))
        assert user.role == 'admin'
        assert hasher.verify('ExampleTestPassword42!',user.password_hash)
        previous_hash = user.password_hash
        monkeypatch.setenv('BOOTSTRAP_ADMIN_PASSWORD','AnotherTestPassword42!')
        bootstrap_admin(session)
        session.refresh(user)
        assert user.password_hash == previous_hash
        assert len(session.scalars(select(User)).all()) == 1

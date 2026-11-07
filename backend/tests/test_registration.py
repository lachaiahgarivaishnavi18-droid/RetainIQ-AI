from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool
from app.core import Base, db
from app.main import app, register, Credentials

def test_production_registration_is_opt_in_and_creates_analyst(monkeypatch):
    monkeypatch.setenv('ENVIRONMENT', 'production')
    monkeypatch.delenv('ALLOW_PUBLIC_REGISTRATION', raising=False)
    isolated = create_engine('sqlite://', connect_args={'check_same_thread':False}, poolclass=StaticPool)
    Base.metadata.create_all(isolated)
    def isolated_db():
        with Session(isolated) as session:
            yield session
    app.dependency_overrides[db] = isolated_db
    try:
        with TestClient(app) as client:
            credentials = {'email': 'new-member@example.com', 'password': 'MemberTestPassword42!'}
            assert client.post('/api/auth/register', json=credentials).status_code == 403
            monkeypatch.setenv('ALLOW_PUBLIC_REGISTRATION', 'true')
            response = client.post('/api/auth/register', json=credentials)
            assert response.status_code == 201, response.text
            assert response.json()['user']['role'] == 'analyst'
            assert client.post('/api/auth/register', json=credentials).status_code == 409
            assert client.post('/api/auth/register', json={**credentials, 'role': 'admin'}).status_code == 422
            client.headers['Authorization'] = 'Bearer ' + response.json()['access_token']
            assert client.get('/api/auth/me').json()['role'] == 'analyst'
            assert client.get('/api/users').status_code == 403
            assert client.post('/api/retention/approve', json={'kind':'campaign','id':'1','approved':True}).status_code == 403
            login = client.post('/api/auth/login', json=credentials)
            assert login.status_code == 200
    finally:
        app.dependency_overrides.pop(db, None)

def test_production_signup_never_bootstraps_an_administrator(monkeypatch):
    monkeypatch.setenv('ENVIRONMENT', 'production')
    monkeypatch.setenv('ALLOW_PUBLIC_REGISTRATION', 'true')
    isolated = create_engine('sqlite://')
    Base.metadata.create_all(isolated)
    with Session(isolated) as session:
        response = register(Credentials(email='first-member@example.com', password='MemberTestPassword42!'), session)
        assert response['user']['role'] == 'analyst'

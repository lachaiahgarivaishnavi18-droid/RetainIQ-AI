import os
import secrets
from datetime import datetime, timezone, timedelta
from pathlib import Path

import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pwdlib import PasswordHash
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import DeclarativeBase, sessionmaker, Session

RUNTIME = Path(os.getenv('RUNTIME_DIR', Path(__file__).resolve().parents[1] / 'runtime'))
RUNTIME.mkdir(parents=True, exist_ok=True)
DATABASE_URL = os.getenv('DATABASE_URL', f'sqlite:///{(RUNTIME / "retainiq.db").as_posix()}')
engine = create_engine(DATABASE_URL, connect_args={'check_same_thread': False} if DATABASE_URL.startswith('sqlite') else {})
if DATABASE_URL.startswith('sqlite'):
    @event.listens_for(engine, 'connect')
    def sqlite_fk(conn, _):
        conn.execute('PRAGMA foreign_keys=ON')
SessionLocal = sessionmaker(engine, expire_on_commit=False)

class Base(DeclarativeBase):
    pass

def now():
    return datetime.now(timezone.utc).isoformat()

def db():
    with SessionLocal() as session:
        yield session

secret_file = RUNTIME / '.jwt_secret'
if not os.getenv('JWT_SECRET') and not secret_file.exists():
    secret_file.write_text(secrets.token_urlsafe(48))
SECRET = os.getenv('JWT_SECRET') or secret_file.read_text()
if os.getenv('ENVIRONMENT') == 'production' and (not os.getenv('JWT_SECRET') or len(SECRET) < 48 or SECRET.startswith('replace-')):
    raise RuntimeError('Set a unique JWT_SECRET of at least 48 characters in production')
hasher = PasswordHash.recommended()
bearer = HTTPBearer(auto_error=False)

def token(user):
    return jwt.encode({'sub': str(user.id), 'exp': datetime.now(timezone.utc) + timedelta(hours=8)}, SECRET, algorithm='HS256')

def current_user(auth: HTTPAuthorizationCredentials = Depends(bearer), session: Session = Depends(db)):
    from .models import User
    try:
        claims = jwt.decode(auth.credentials if auth else '', SECRET, algorithms=['HS256'])
        user = session.get(User, int(claims['sub']))
        if not user:
            raise ValueError('Unknown user')
        return user
    except (jwt.PyJWTError, ValueError, KeyError):
        raise HTTPException(401, 'Please log in')

def roles(*allowed):
    def check(user=Depends(current_user)):
        if user.role not in allowed:
            raise HTTPException(403, 'This action requires an authorized role')
        return user
    return check

def audit(session, user, action, details):
    from .models import Audit
    session.add(Audit(user_id=user.id if user else None, action=action, details=details))
    session.commit()

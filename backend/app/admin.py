"""Provision an administrator without exposing a public production signup endpoint."""
import getpass
import os
from sqlalchemy import select
from .core import SessionLocal, hasher, audit
from .models import User

def bootstrap_admin(session):
    """Opt-in first account provisioning. Existing users/passwords are never changed."""
    email = os.getenv('BOOTSTRAP_ADMIN_EMAIL', '').strip().lower()
    password = os.getenv('BOOTSTRAP_ADMIN_PASSWORD', '')
    if not email and not password:
        return
    if session.scalar(select(User.id).limit(1)):
        return
    if '@' not in email or len(password) < 16:
        raise RuntimeError('Bootstrap admin requires an email and a password of at least 16 characters')
    user = User(email=email, password_hash=hasher.hash(password), role='admin')
    session.add(user)
    session.commit()
    audit(session, user, 'administrator_bootstrapped', {'source': 'hosting secret settings'})

if __name__ == '__main__':
    email = input('Administrator email: ').strip().lower()
    password = getpass.getpass('Password (10+ characters): ')
    if '@' not in email or len(password) < 10:
        raise SystemExit('Invalid email or password length')
    with SessionLocal() as session:
        if session.scalar(select(User).where(User.email == email)):
            raise SystemExit('Account already exists')
        session.add(User(email=email, password_hash=hasher.hash(password), role='admin'))
        session.commit()
    print('Administrator created')

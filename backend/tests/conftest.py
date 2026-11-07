import os
import tempfile

# Establish isolation before any app module is imported during test collection.
os.environ['RUNTIME_DIR'] = tempfile.mkdtemp(prefix='retainiq-test-')
os.environ['DATABASE_URL'] = 'sqlite:///' + os.path.join(os.environ['RUNTIME_DIR'], 'test.db').replace('\\', '/')
os.environ['ENVIRONMENT'] = 'test'
os.environ.pop('BOOTSTRAP_ADMIN_EMAIL', None)
os.environ.pop('BOOTSTRAP_ADMIN_PASSWORD', None)

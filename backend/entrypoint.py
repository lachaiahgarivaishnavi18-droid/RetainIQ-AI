"""Initialize mounted-volume ownership, then run migrations/API without root privileges."""
import os
import pwd
import subprocess
import sys
from pathlib import Path

def main():
    runtime = Path(os.environ.get('RUNTIME_DIR', '/app/runtime'))
    runtime.mkdir(parents=True, exist_ok=True)
    if os.getuid() == 0:
        account = pwd.getpwnam('appuser')
        os.chown(runtime, account.pw_uid, account.pw_gid)
        os.setgroups([])
        os.setgid(account.pw_gid)
        os.setuid(account.pw_uid)
    port = os.environ.get('PORT', '8000')
    if not port.isdigit() or not 1 <= int(port) <= 65535:
        raise RuntimeError('PORT must be between 1 and 65535')
    subprocess.run([sys.executable, '-m', 'alembic', 'upgrade', 'head'], check=True)
    os.execv(sys.executable, [sys.executable, '-m', 'uvicorn', 'app.main:app', '--host', '0.0.0.0', '--port', port])

if __name__ == '__main__':
    main()

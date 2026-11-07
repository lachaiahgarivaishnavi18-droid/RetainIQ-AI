"""Launch browser verification without writing credentials to disk or CLI arguments."""
import getpass
import json
import shutil
import subprocess
import sys
from pathlib import Path

credentials = json.loads(getpass.getpass('Demo credentials JSON (hidden): '))
root = Path(__file__).resolve().parents[1]
subprocess.run([shutil.which('node'), str(root / 'frontend/scripts/verify-hosted.cjs'), sys.argv[1]], input=json.dumps(credentials), text=True, check=True)

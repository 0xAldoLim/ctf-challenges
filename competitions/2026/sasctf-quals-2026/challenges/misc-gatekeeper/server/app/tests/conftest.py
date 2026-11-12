import sys
from pathlib import Path

# Make the screener package (server/app/verifier) importable as a top-level
# package when running pytest from anywhere.
APP_ROOT = Path(__file__).resolve().parents[1]
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

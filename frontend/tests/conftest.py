import sys
from pathlib import Path

# Make the frontend's own modules (services, agent) importable when pytest runs from the repo root.
FRONTEND_DIR = Path(__file__).resolve().parents[1]
if str(FRONTEND_DIR) not in sys.path:
    sys.path.insert(0, str(FRONTEND_DIR))

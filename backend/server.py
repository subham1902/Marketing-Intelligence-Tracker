"""Emergent-style backend entrypoint.

Emergent's template runs `uvicorn server:app --host 0.0.0.0 --port 8001` from
/app/backend. This adapter exposes the real FastAPI app (api/main.py) without
moving any code. All routes are also served under /api.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from api.main import app  # noqa: E402,F401

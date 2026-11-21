"""Runtime configuration, read from environment variables with sane defaults."""

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.environ.get("UPSOLVE_DATA_DIR", ROOT / "data"))
DB_PATH = Path(os.environ.get("UPSOLVE_DB", DATA_DIR / "upsolve.db"))
MODEL_PATH = Path(os.environ.get("UPSOLVE_MODEL", DATA_DIR / "model.json"))
STATIC_DIR = ROOT / "static"
PLUGINS_DIR = Path(os.environ.get("UPSOLVE_PLUGINS_DIR", ROOT / "plugins"))

CF_API = os.environ.get("UPSOLVE_CF_API", "https://codeforces.com/api")
# Codeforces asks clients to stay at or below one request every two seconds.
CF_MIN_INTERVAL = float(os.environ.get("UPSOLVE_CF_INTERVAL", "2.1"))
PROBLEMSET_TTL_HOURS = 24

# Comma-separated list of origins allowed to call the API from a browser.
CORS_ORIGINS = [o.strip() for o in os.environ.get("UPSOLVE_CORS_ORIGINS", "*").split(",") if o.strip()]

# An attempt counts as solved when accepted within this window after the first eligible submission.
SOLVE_WINDOW_SECONDS = 24 * 3600
TARGET_LOW, TARGET_HIGH = 0.50, 0.70
MAX_FOCUS_TOPICS = 2

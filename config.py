"""
Global config — credentials are loaded from .env (never commit that file).

Setup:
  1. Copy .env.example → .env
  2. Fill in your Gmail App Password (myaccount.google.com/security → App passwords)
  3. Set your sender + recipient email addresses
"""
import os
from pathlib import Path

# Load .env if present (simple key=value, no external dependency)
_env = Path(__file__).parent / ".env"
if _env.exists():
    for _line in _env.read_text().splitlines():
        _line = _line.strip()
        if _line and not _line.startswith("#") and "=" in _line:
            _k, _v = _line.split("=", 1)
            os.environ.setdefault(_k.strip(), _v.strip())

# ── Email ──────────────────────────────────────────────────────────────────────
GMAIL_SENDER       = os.environ["GMAIL_SENDER"]
GMAIL_APP_PASSWORD = os.environ["GMAIL_APP_PASSWORD"]
GMAIL_RECIPIENT    = os.environ["GMAIL_RECIPIENT"]

# ── Daemon ─────────────────────────────────────────────────────────────────────
SCAN_INTERVAL_SECONDS = 20 * 60  # scan every 20 minutes
MIN_SCORE_TO_EMAIL    = 70       # only email jobs scoring >= this
MAX_EMAILS_PER_SCAN   = 3        # cap per cycle so Gemma isn't running all night
DB_KEEP_TOP           = 5        # keep only the top N jobs in the DB (newest + highest score)

# ── Scanner defaults ───────────────────────────────────────────────────────────
DEFAULT_ROLES   = ["Software Engineer", "ML Engineer", "Backend Engineer"]
REMOTE_ONLY     = True
MIN_SCORE_SAVE  = 45             # jobs below this are not saved at all

# ── LLM (LM Studio) ────────────────────────────────────────────────────────────
LLM_BASE_URL = os.environ.get("LLM_BASE_URL", "http://192.168.86.22:1234/v1")
LLM_MODEL    = os.environ.get("LLM_MODEL",    "gemma-3-27b-it")

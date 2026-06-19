"""
Global config — values are loaded from .env (never commit that file).

Setup:
  1. Copy .env.example → .env
  2. Set your LLM endpoint (LLM_BASE_URL / LLM_MODEL)
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

# ── Daemon ─────────────────────────────────────────────────────────────────────
SCAN_INTERVAL_SECONDS = 20 * 60  # scan every 20 minutes

# ── Scanner defaults ───────────────────────────────────────────────────────────
# Roles query the aggregator / HN feeds (the ATS watchlist is fixed). Approval is
# decided by the LLM criteria in job_scanner/quality.py, not by a numeric score.
DEFAULT_ROLES   = ["Software Engineer", "ML Engineer", "Backend Engineer"]
MIN_SCORE_GOOD  = 70             # approved jobs at/above this fit score are flagged "strong"
MAX_SCREEN_CONCURRENCY = 3       # concurrent jobs sent to the local LLM during a scan

# ── LLM (LM Studio) ────────────────────────────────────────────────────────────
LLM_BASE_URL = os.environ.get("LLM_BASE_URL", "http://192.168.86.22:1234/v1")
LLM_MODEL    = os.environ.get("LLM_MODEL",    "gemma-3-27b-it")

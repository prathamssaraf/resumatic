"""
Storage for the Google XR tracker page — INTENTIONALLY separate from
job_scanner/store.py's `jobs` table. Same SQLite file, its own table, so this
feature can never interact with (or slow down) the normal scan/screen/dashboard
flow. No LLM screening touches this data; filtering is deterministic (see
job_scanner/sources/google_xr.py).
"""
from __future__ import annotations
import hashlib
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "data" / "jobs.db"


def _conn() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(DB_PATH, timeout=30)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA journal_mode=WAL")
    c.execute("PRAGMA busy_timeout=30000")
    c.execute("""
        CREATE TABLE IF NOT EXISTS xr_jobs (
            id TEXT PRIMARY KEY,
            title TEXT,
            company TEXT DEFAULT 'Google',
            url TEXT UNIQUE,
            location TEXT,
            posted_date TEXT,
            description TEXT,
            fetched_at TEXT DEFAULT (datetime('now'))
        )
    """)
    c.commit()
    return c


def _xr_job_id(url: str) -> str:
    return hashlib.md5(url.encode()).hexdigest()[:16]


def existing_xr_urls() -> set[str]:
    c = _conn()
    rows = c.execute("SELECT url FROM xr_jobs").fetchall()
    c.close()
    return {r[0] for r in rows}


def save_xr_jobs(jobs: list[dict]) -> tuple[int, int]:
    """Insert new XR jobs. Returns (inserted, duplicate) counts."""
    c = _conn()
    inserted = dupes = 0
    for j in jobs:
        jid = _xr_job_id(j["url"])
        try:
            c.execute("""
                INSERT INTO xr_jobs (id, title, company, url, location, posted_date, description)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                jid, j.get("title", ""), j.get("company", "Google"), j["url"],
                j.get("location", ""), j.get("posted_date", ""), j.get("description", ""),
            ))
            inserted += 1
        except sqlite3.IntegrityError:
            dupes += 1
    c.commit()
    c.close()
    return inserted, dupes


def list_xr_jobs(limit: int = 300) -> list[dict]:
    c = _conn()
    rows = c.execute(
        "SELECT * FROM xr_jobs ORDER BY posted_date DESC, fetched_at DESC LIMIT ?", (limit,)
    ).fetchall()
    c.close()
    return [dict(r) for r in rows]


def xr_stats() -> dict:
    c = _conn()
    total = c.execute("SELECT COUNT(*) FROM xr_jobs").fetchone()[0]
    latest = c.execute("SELECT MAX(fetched_at) FROM xr_jobs").fetchone()[0]
    c.close()
    return {"total": total, "last_scan": latest}

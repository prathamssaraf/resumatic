"""
Tracks every LinkedIn job ID we've ever inspected via the authenticated
redirect-resolution step — regardless of outcome (easy_apply, no_redirect,
duplicate_destination, or saved). This is the FIRST dedup layer: it means a
LinkedIn listing we already checked (even one that got bumped/reposted under
the same ID) is never re-opened with the authenticated session every cycle.

The SECOND dedup layer is the normal one: once a redirect resolves to a real
employer URL, that URL is checked against job_scanner.store.existing_urls()
before being queued, so the same posting found via LinkedIn and via a direct
ATS scraper never gets saved twice.
"""
from __future__ import annotations
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "data" / "jobs.db"


def _conn() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(DB_PATH, timeout=30)
    c.execute("PRAGMA journal_mode=WAL")
    c.execute("PRAGMA busy_timeout=30000")
    c.execute("""
        CREATE TABLE IF NOT EXISTS linkedin_seen (
            job_id TEXT PRIMARY KEY,
            outcome TEXT,
            checked_at TEXT DEFAULT (datetime('now'))
        )
    """)
    c.commit()
    return c


def existing_linkedin_ids() -> set[str]:
    c = _conn()
    rows = c.execute("SELECT job_id FROM linkedin_seen").fetchall()
    c.close()
    return {r[0] for r in rows}


def mark_seen(job_id: str, outcome: str) -> None:
    c = _conn()
    try:
        c.execute("INSERT INTO linkedin_seen (job_id, outcome) VALUES (?, ?)", (job_id, outcome))
        c.commit()
    except sqlite3.IntegrityError:
        pass
    c.close()

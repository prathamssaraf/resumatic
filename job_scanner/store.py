"""
SQLite store for found jobs.
Simple — no vector DB, no embeddings.
"""
from __future__ import annotations
import sqlite3
import json
import hashlib
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "data" / "jobs.db"


def _conn() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    c.execute("""
        CREATE TABLE IF NOT EXISTS jobs (
            id TEXT PRIMARY KEY,
            title TEXT,
            company TEXT,
            url TEXT UNIQUE,
            platform TEXT,
            description TEXT,
            location TEXT,
            salary TEXT,
            posted_date TEXT,
            score INTEGER,
            score_reason TEXT,
            status TEXT DEFAULT 'new',
            created_at TEXT DEFAULT (datetime('now'))
        )
    """)
    c.commit()
    return c


def _job_id(job: dict) -> str:
    return hashlib.md5(job.get("url", job.get("title", "")).encode()).hexdigest()[:16]


def save_jobs(jobs: list[dict]) -> tuple[int, int]:
    """Insert new jobs. Returns (inserted, duplicate) counts."""
    c = _conn()
    inserted = dupes = 0
    for j in jobs:
        jid = _job_id(j)
        try:
            c.execute("""
                INSERT INTO jobs (id, title, company, url, platform, description,
                                  location, salary, posted_date, score, score_reason)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                jid, j.get("title", ""), j.get("company", ""), j.get("url", ""),
                j.get("platform", ""), j.get("description", ""), j.get("location", ""),
                j.get("salary", ""), j.get("posted_date", ""),
                j.get("score", 0), j.get("score_reason", ""),
            ))
            inserted += 1
        except sqlite3.IntegrityError:
            dupes += 1
    c.commit()
    c.close()
    return inserted, dupes


def list_jobs(status: str | None = None, limit: int = 50) -> list[dict]:
    c = _conn()
    if status:
        rows = c.execute(
            "SELECT * FROM jobs WHERE status=? ORDER BY posted_date DESC, score DESC, created_at DESC LIMIT ?",
            (status, limit)
        ).fetchall()
    else:
        rows = c.execute(
            "SELECT * FROM jobs ORDER BY posted_date DESC, score DESC, created_at DESC LIMIT ?", (limit,)
        ).fetchall()
    c.close()
    return [dict(r) for r in rows]


def get_job(job_id: str) -> dict | None:
    c = _conn()
    row = c.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
    c.close()
    return dict(row) if row else None


def update_status(job_id: str, status: str) -> None:
    c = _conn()
    c.execute("UPDATE jobs SET status=? WHERE id=?", (status, job_id))
    c.commit()
    c.close()


def prune_to_top_n(n: int) -> int:
    """Keep only the top N jobs (newest + highest score). Returns number deleted."""
    c = _conn()
    rows = c.execute(
        "SELECT id FROM jobs ORDER BY posted_date DESC, score DESC, created_at DESC"
    ).fetchall()
    keep_ids = {r[0] for r in rows[:n]}
    all_ids  = {r[0] for r in rows}
    to_delete = all_ids - keep_ids
    if to_delete:
        c.execute(f"DELETE FROM jobs WHERE id IN ({','.join('?'*len(to_delete))})", list(to_delete))
        c.commit()
    c.close()
    return len(to_delete)


def stats() -> dict:
    c = _conn()
    total = c.execute("SELECT COUNT(*) FROM jobs").fetchone()[0]
    by_status = dict(c.execute(
        "SELECT status, COUNT(*) FROM jobs GROUP BY status"
    ).fetchall())
    by_platform = dict(c.execute(
        "SELECT platform, COUNT(*) FROM jobs GROUP BY platform"
    ).fetchall())
    c.close()
    return {"total": total, "by_status": by_status, "by_platform": by_platform}

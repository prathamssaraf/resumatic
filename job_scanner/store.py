"""
SQLite store for found jobs.
Simple — no vector DB, no embeddings.
"""
from __future__ import annotations
import sqlite3
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
            created_at TEXT DEFAULT (datetime('now')),
            resume_path TEXT DEFAULT '',
            cover_path TEXT DEFAULT ''
        )
    """)
    # Migrate existing DBs that don't have the new columns
    for col in ("resume_path", "cover_path"):
        try:
            c.execute(f"ALTER TABLE jobs ADD COLUMN {col} TEXT DEFAULT ''")
        except Exception:
            pass
    c.commit()
    return c


def job_id(job: dict) -> str:
    # Deduplicate on (company + title) so the same role from different sources
    # (e.g. Simplify + direct ATS) doesn't get saved twice.
    company = (job.get("company") or "").strip().lower()
    title   = (job.get("title")   or "").strip().lower()
    key = f"{company}|{title}" if (company and title) else job.get("url", job.get("title", ""))
    return hashlib.md5(key.encode()).hexdigest()[:16]


# Backwards-compatible alias
_job_id = job_id


def existing_job_ids() -> set[str]:
    """All job IDs already in the DB — used to skip re-processing known jobs."""
    c = _conn()
    rows = c.execute("SELECT id FROM jobs").fetchall()
    c.close()
    return {r[0] for r in rows}


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


def set_job_docs(job_id: str, resume_path: str, cover_path: str) -> None:
    c = _conn()
    c.execute(
        "UPDATE jobs SET resume_path=?, cover_path=? WHERE id=?",
        (resume_path, cover_path, job_id)
    )
    c.commit()
    c.close()


def expire_old_jobs(max_age_days: int = 10) -> int:
    """Mark 'new' jobs older than max_age_days as 'skip' so they never get built."""
    c = _conn()
    c.execute(
        "UPDATE jobs SET status='skip' WHERE status='new' AND posted_date != '' "
        "AND posted_date < datetime('now', ?)",
        (f"-{max_age_days} days",)
    )
    count = c.total_changes
    c.commit()
    c.close()
    return count


def claim_next_build_job(min_score: int, exclude_ids: set[str]) -> dict | None:
    """
    Atomically claim the highest-score 'new' job for building.
    Only picks jobs posted within the last 10 days.
    Marks it 'building' so concurrent calls never double-process.
    Returns the job dict or None if queue is empty.
    """
    c = _conn()
    placeholders = ",".join("?" * len(exclude_ids)) if exclude_ids else "NULL"
    query = f"""
        SELECT * FROM jobs
        WHERE status='new' AND score >= ?
        AND (posted_date = '' OR posted_date >= datetime('now', '-10 days'))
        {"AND id NOT IN (" + placeholders + ")" if exclude_ids else ""}
        ORDER BY score DESC, created_at ASC
        LIMIT 1
    """
    params = [min_score] + list(exclude_ids)
    row = c.execute(query, params).fetchone()
    if not row:
        c.close()
        return None
    job = dict(row)
    c.execute("UPDATE jobs SET status='building' WHERE id=? AND status='new'", (job["id"],))
    claimed = c.total_changes > 0
    c.commit()
    c.close()
    return job if claimed else None


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

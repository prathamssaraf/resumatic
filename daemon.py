"""
Daemon — scans every 20 minutes, auto-builds resumes for top matches, emails results.

Run: uv run python main.py daemon
Stop: Ctrl+C
"""
from __future__ import annotations
import asyncio
import json
import time
from pathlib import Path
from rich.console import Console
from rich.rule import Rule

_STATUS_FILE = Path("data/active_build.json")


def _write_build_status(company: str, title: str, message: str) -> None:
    try:
        _STATUS_FILE.parent.mkdir(parents=True, exist_ok=True)
        _STATUS_FILE.write_text(json.dumps({
            "source": "daemon",
            "company": company,
            "title": title,
            "message": message,
            "started": time.time(),
        }))
    except Exception:
        pass


def _clear_build_status() -> None:
    try:
        _STATUS_FILE.unlink(missing_ok=True)
    except Exception:
        pass

import config
from job_scanner.scanner import run_scan
from job_scanner.store import list_jobs, update_status, stats, prune_to_top_n
from notifier import send_job_email

console = Console()


def _find_pdfs(company: str) -> tuple[Path | None, Path | None]:
    """Find the most recently generated PDF pair for a company."""
    from resume_builder.utils import sanitize_filename
    out = Path("output")
    safe = sanitize_filename(company)
    resume  = out / "resumes"       / f"Pratham_Saraf_Resume_{safe}.pdf"
    cover   = out / "cover_letters" / f"Pratham_Saraf_CoverLetter_{safe}.pdf"
    return (resume if resume.exists() else None,
            cover  if cover.exists()  else None)


def _build_resume_for_job(job: dict) -> tuple[Path | None, Path | None]:
    """Run the full resume pipeline for a job. Returns (resume_pdf, cover_pdf)."""
    from graph.db import init_db
    from graph.schema import create_schema
    from resume_builder.pipeline import run_pipeline

    conn = init_db()
    create_schema(conn)

    desc = job.get("description", "")
    if len(desc) < 200:
        # Description too thin to build a good resume — skip
        return None, None

    run_pipeline(desc, compile_pdf=True, generate_cover=True)
    return _find_pdfs(job.get("company", "unknown"))


async def _scan_cycle(cycle: int) -> int:
    """Run one scan cycle. Returns number of emails sent."""
    console.print(Rule(f"[bold]Cycle {cycle}[/bold] — {time.strftime('%H:%M:%S')}"))

    # 1. Scan all sources
    result = await run_scan(
        roles=config.DEFAULT_ROLES,
        remote_only=config.REMOTE_ONLY,
        min_score=config.MIN_SCORE_SAVE,
    )
    new_count = result["inserted"]
    console.print(
        f"  Scan: {result['raw']} raw → {result['after_filter']} passed → "
        f"[cyan]{new_count} new saved[/cyan]"
    )

    # Prune DB — keep only top N by recency + score
    pruned = prune_to_top_n(config.DB_KEEP_TOP)
    if pruned:
        console.print(f"  [dim]Pruned {pruned} older jobs — keeping top {config.DB_KEEP_TOP}[/dim]")

    if new_count == 0:
        console.print("  No new jobs this cycle.")
        return 0

    # 2. Pick top new jobs to email — newest first, then by score
    top_jobs = [
        j for j in list_jobs(status="new", limit=50)
        if j["score"] >= config.MIN_SCORE_TO_EMAIL
    ][:config.MAX_EMAILS_PER_SCAN]
    # list_jobs already sorts by posted_date DESC, score DESC

    if not top_jobs:
        console.print(f"  No jobs above score {config.MIN_SCORE_TO_EMAIL} to email.")
        return 0

    console.print(f"  Building resumes for {len(top_jobs)} top match(es)...")

    emails_sent = 0
    for job in top_jobs:
        title   = job["title"]
        company = job["company"]
        console.print(f"  → [bold]{title}[/bold] @ {company}  (score {job['score']})")
        _write_build_status(company, title, f"Building resume for {title} @ {company}…")

        try:
            resume_pdf, cover_pdf = _build_resume_for_job(job)
        except Exception as e:
            console.print(f"    [red]Resume build failed:[/red] {e}")
            update_status(job["id"], "error")
            _clear_build_status()
            continue

        if not resume_pdf:
            console.print("    [yellow]Skipped — description too thin for resume[/yellow]")
            update_status(job["id"], "skip")
            _clear_build_status()
            continue

        _write_build_status(company, title, "Sending email…")
        ok = send_job_email(job, resume_pdf, cover_pdf)
        if ok:
            console.print(f"    [green]✓ Emailed to {config.GMAIL_RECIPIENT}[/green]")
            emails_sent += 1
        update_status(job["id"], "applied")
        _clear_build_status()

    return emails_sent


async def run_daemon() -> None:
    console.print("[bold green]jobs-auto-scanner daemon started[/bold green]")
    console.print(f"  Scan interval : every {config.SCAN_INTERVAL_SECONDS // 60} minutes")
    console.print(f"  Email threshold: score >= {config.MIN_SCORE_TO_EMAIL}")
    console.print(f"  Max emails/cycle: {config.MAX_EMAILS_PER_SCAN}")
    console.print(f"  Roles: {', '.join(config.DEFAULT_ROLES)}")
    console.print("  Press Ctrl+C to stop.\n")

    s = stats()
    console.print(f"  DB: {s['total']} jobs stored ({s['by_status']})\n")

    cycle = 1
    while True:
        try:
            await _scan_cycle(cycle)
        except Exception as e:
            console.print(f"[red]Cycle {cycle} error:[/red] {e}")

        cycle += 1
        next_run = time.strftime('%H:%M:%S', time.localtime(time.time() + config.SCAN_INTERVAL_SECONDS))
        console.print(f"\n  [dim]Next scan at {next_run}. Sleeping...[/dim]\n")
        await asyncio.sleep(config.SCAN_INTERVAL_SECONDS)

"""
Daemon — scan-only loop.

Scrapes every SCAN_INTERVAL_SECONDS and screens each fresh posting against the
LLM criteria in job_scanner/quality.py (one Gemma call per criterion). Jobs that
pass every criterion are saved as 'approved' with a 0-100 fit score; the rest are
saved as 'rejected'. Review approved jobs in the dashboard.

Run: uv run python main.py daemon
"""
from __future__ import annotations
import asyncio
import time
from pathlib import Path
from rich.console import Console
from rich.rule import Rule

import config
from job_scanner.scanner import run_scan
from job_scanner.store import stats, expire_old_jobs


console = Console()


# ── Scan loop ─────────────────────────────────────────────────────────────────

async def _scan_loop(scan_interval: int) -> None:
    """Scrapes every scan_interval seconds and saves qualifying jobs to the DB."""
    cycle = 1
    while True:
        console.print(Rule(f"[bold cyan]Scan {cycle}[/bold cyan] — {time.strftime('%H:%M:%S')}"))
        try:
            expired = await asyncio.get_running_loop().run_in_executor(None, expire_old_jobs, 10)
            if expired:
                console.print(f"  [dim]Expired {expired} job(s) older than 10 days → skip[/dim]")
            result = await run_scan(
                roles=config.DEFAULT_ROLES,
                max_concurrent=config.MAX_SCREEN_CONCURRENCY,
            )
            console.print(
                f"  Scan: {result['raw']} raw → {result['candidates']} screened → "
                f"[green]{result['approved']} approved[/green], "
                f"[dim]{result['rejected']} rejected[/dim]"
            )
            if result["approved"] == 0:
                console.print("  No new approved jobs this scan.")
        except Exception as e:
            console.print(f"[red]Scan {cycle} error:[/red] {e}")

        cycle += 1
        next_run = time.strftime('%H:%M:%S', time.localtime(time.time() + scan_interval))
        console.print(f"  [dim]Next scan at {next_run}[/dim]\n")
        await asyncio.sleep(scan_interval)


# ── Entry point ───────────────────────────────────────────────────────────────

async def run_daemon() -> None:
    import os
    _PID_FILE = Path("data/daemon.pid")
    try:
        _PID_FILE.parent.mkdir(parents=True, exist_ok=True)
        _PID_FILE.write_text(str(os.getpid()))
    except Exception:
        pass

    from job_scanner.quality import CRITERIA
    console.print("[bold green]Jobs scanner daemon started[/bold green]")
    console.print(f"  Scan every   : {config.SCAN_INTERVAL_SECONDS // 60} minutes")
    console.print(f"  Criteria     : {len(CRITERIA)} LLM checks per job (approve if all pass)")
    console.print(f"  Strong match : fit score >= {config.MIN_SCORE_GOOD}")
    console.print(f"  Roles        : {', '.join(config.DEFAULT_ROLES)}\n")

    s = stats()
    console.print(f"  DB: {s['total']} jobs  {s['by_status']}\n")

    await _scan_loop(config.SCAN_INTERVAL_SECONDS)

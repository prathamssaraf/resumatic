#!/usr/bin/env python3
"""
Jobs Auto Scanner — CLI entry point.

Usage:
  uv run python main.py scan --roles "ML Engineer" "Backend SWE"
  uv run python main.py scan --roles "Software Engineer" --no-remote
  uv run python main.py list
  uv run python main.py list --status new
  uv run python main.py daemon
  uv run python main.py dashboard
"""
import asyncio
import argparse


def cmd_scan(args: argparse.Namespace) -> None:
    from job_scanner.scanner import run_scan, print_results
    roles = args.roles or ["Software Engineer", "ML Engineer"]
    result = asyncio.run(run_scan(
        roles=roles,
        include_aggregators=not args.no_aggregators,
        include_hn=not args.no_hn,
        include_simplify=not args.no_simplify,
        include_citi=not args.no_citi,
        include_workday=not args.no_workday,
        include_bigtech=not args.no_bigtech,
        include_meta=not args.no_meta,
    ))
    print_results(result)


def cmd_meta(args: argparse.Namespace) -> None:
    """On-demand browser-driven pull of Meta (metacareers.com) jobs."""
    from job_scanner.sources.meta import scrape_meta
    from job_scanner.quality import evaluate_job
    from job_scanner.store import save_jobs
    from rich.console import Console
    console = Console()

    async def run():
        console.print("[cyan]Launching browser to pull Meta jobs…[/cyan]")
        jobs = await scrape_meta(max_detail=args.max, headless=not args.show)
        console.print(f"  Pulled [cyan]{len(jobs)}[/cyan] new US technical Meta jobs. Screening…")
        loop = asyncio.get_running_loop()
        sem = asyncio.Semaphore(3)
        approved = 0

        async def screen(job):
            nonlocal approved
            async with sem:
                try:
                    v = await loop.run_in_executor(None, evaluate_job, job)
                except Exception as e:
                    console.print(f"  [dim]✗ {job['title'][:40]} — {str(e)[:40]}[/dim]")
                    return
            job["score"] = v["score"]; job["score_reason"] = v["reason"]
            job["status"] = "approved" if v["approved"] else "rejected"
            await loop.run_in_executor(None, save_jobs, [job])
            if v["approved"]:
                approved += 1
                console.print(f"  [green]✓ APPROVED[/green] {job['title'][:44]} [dim](fit {v['score']})[/dim]")
            else:
                console.print(f"  [dim]· rejected {job['title'][:44]} [{v['failed']}][/dim]")

        await asyncio.gather(*[screen(j) for j in jobs])
        console.print(f"\n[bold]Meta pull complete[/bold] — {approved} approved, {len(jobs)-approved} rejected. See the dashboard.")

    asyncio.run(run())


def cmd_xr_scan(args: argparse.Namespace) -> None:
    """Standalone Google XR/AR/VR tracker scan — separate table, no LLM, no daemon."""
    from job_scanner.sources.google_xr import scrape_google_xr
    from job_scanner.xr_store import save_xr_jobs
    from rich.console import Console
    console = Console()

    async def run():
        console.print("[cyan]Scanning Google for XR/AR/VR roles (non-senior, US-only)…[/cyan]")
        jobs = await scrape_google_xr()
        ins, dup = save_xr_jobs(jobs)
        console.print(f"[bold]Done[/bold] — {len(jobs)} found, {ins} new, {dup} already tracked. See the dashboard's Google XR tab.")

    asyncio.run(run())


def cmd_list(args: argparse.Namespace) -> None:
    from job_scanner.scanner import print_job_list
    print_job_list(status=args.status)


def cmd_daemon(args: argparse.Namespace) -> None:
    from daemon import run_daemon
    asyncio.run(run_daemon())


def cmd_dashboard(args: argparse.Namespace) -> None:
    from dashboard import run_dashboard
    run_dashboard(port=args.port)


def main() -> None:
    parser = argparse.ArgumentParser(description="Jobs Auto Scanner")
    sub = parser.add_subparsers(dest="command", required=True)

    # scan
    scan_p = sub.add_parser("scan", help="Scan job boards and save new leads")
    scan_p.add_argument("--roles", nargs="+", default=None,
                        help='Role keywords, e.g. --roles "ML Engineer" "Backend SWE"')
    scan_p.add_argument("--no-aggregators", action="store_true", help="Skip RemoteOK/Remotive/Jobicy")
    scan_p.add_argument("--no-hn", action="store_true", help="Skip Hacker News")
    scan_p.add_argument("--no-simplify", action="store_true", help="Skip SimplifyJobs feed")
    scan_p.add_argument("--no-citi", action="store_true", help="Skip Citi grad programs")
    scan_p.add_argument("--no-workday", action="store_true", help="Skip Workday employers")
    scan_p.add_argument("--no-bigtech", action="store_true", help="Skip Amazon/Netflix/Google")
    scan_p.add_argument("--no-meta", action="store_true", help="Skip Meta (browser-driven)")
    scan_p.set_defaults(func=cmd_scan)

    # meta (browser-driven, on-demand)
    meta_p = sub.add_parser("meta", help="Browser-driven pull of Meta (metacareers.com) jobs")
    meta_p.add_argument("--max", type=int, default=120, help="Max job detail pages to fetch")
    meta_p.add_argument("--show", action="store_true", help="Show the browser window (non-headless)")
    meta_p.set_defaults(func=cmd_meta)

    # xr-scan (standalone, separate table, no LLM/daemon involvement)
    xr_p = sub.add_parser("xr-scan", help="Scan Google for XR/AR/VR roles (non-senior, US-only)")
    xr_p.set_defaults(func=cmd_xr_scan)

    # list
    list_p = sub.add_parser("list", help="List saved jobs")
    list_p.add_argument("--status", choices=["new", "applied", "skip"], default=None)
    list_p.set_defaults(func=cmd_list)

    # daemon
    daemon_p = sub.add_parser("daemon", help="Run continuous scan loop")
    daemon_p.set_defaults(func=cmd_daemon)

    # dashboard
    dash_p = sub.add_parser("dashboard", help="Open web dashboard at localhost:8765")
    dash_p.add_argument("--port", type=int, default=8765)
    dash_p.set_defaults(func=cmd_dashboard)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()

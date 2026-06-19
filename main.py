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
    ))
    print_results(result)


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
    scan_p.set_defaults(func=cmd_scan)

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

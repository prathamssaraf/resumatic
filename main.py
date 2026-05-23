#!/usr/bin/env python3
"""
Jobs Auto Scanner — CLI entry point.

Usage:
  uv run python main.py resume --file path/to/jd.txt
  uv run python main.py scan --roles "ML Engineer" "Backend SWE"
  uv run python main.py scan --roles "Software Engineer" --no-remote
  uv run python main.py list
  uv run python main.py list --status new
  uv run python main.py apply <job-id>
  uv run python main.py seed
"""
import sys
import asyncio
import argparse
from pathlib import Path


def cmd_resume(args: argparse.Namespace) -> None:
    from graph.db import init_db
    from graph.schema import create_schema
    from resume_builder.pipeline import run_pipeline

    conn = init_db()
    create_schema(conn)

    if args.file:
        jd_text = Path(args.file).read_text(encoding="utf-8")
    elif args.jd:
        jd_text = " ".join(args.jd)
    else:
        print("Error: provide --file or pass the JD as positional argument.")
        sys.exit(1)

    run_pipeline(
        jd_text,
        compile_pdf=not args.no_compile,
        generate_cover=not args.no_cover,
    )


def cmd_seed(args: argparse.Namespace) -> None:
    from graph.seed import run
    run()


def cmd_scan(args: argparse.Namespace) -> None:
    from job_scanner.scanner import run_scan, print_results
    roles = args.roles or ["Software Engineer", "ML Engineer"]
    result = asyncio.run(run_scan(
        roles=roles,
        remote_only=not args.no_remote,
        min_score=args.min_score,
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


def cmd_apply(args: argparse.Namespace) -> None:
    """Pull a saved job's description and run the resume builder on it."""
    from job_scanner.store import get_job, update_status
    from graph.db import init_db
    from graph.schema import create_schema
    from resume_builder.pipeline import run_pipeline

    job = get_job(args.job_id)
    if not job:
        print(f"Job {args.job_id!r} not found. Run `list` to see IDs.")
        sys.exit(1)

    print(f"Applying to: {job['title']} @ {job['company']}")
    print(f"URL: {job['url']}\n")

    conn = init_db()
    create_schema(conn)
    run_pipeline(
        job["description"],
        compile_pdf=not args.no_compile,
        generate_cover=not args.no_cover,
    )
    update_status(args.job_id, "applied")


def main() -> None:
    parser = argparse.ArgumentParser(description="Jobs Auto Scanner")
    sub = parser.add_subparsers(dest="command", required=True)

    # resume
    resume_p = sub.add_parser("resume", help="Generate tailored resume from a JD")
    resume_p.add_argument("jd", nargs="*", help="JD text (or use --file)")
    resume_p.add_argument("--file", "-f", help="Path to .txt file with the JD")
    resume_p.add_argument("--no-compile", action="store_true", help="Skip xelatex compilation")
    resume_p.add_argument("--no-cover", action="store_true", help="Skip cover letter")
    resume_p.set_defaults(func=cmd_resume)

    # scan
    scan_p = sub.add_parser("scan", help="Scan job boards and save new leads")
    scan_p.add_argument("--roles", nargs="+", default=None,
                        help='Role keywords, e.g. --roles "ML Engineer" "Backend SWE"')
    scan_p.add_argument("--no-remote", action="store_true", help="Include non-remote jobs")
    scan_p.add_argument("--no-aggregators", action="store_true", help="Skip RemoteOK/Remotive/Jobicy")
    scan_p.add_argument("--no-hn", action="store_true", help="Skip Hacker News")
    scan_p.add_argument("--no-simplify", action="store_true", help="Skip SimplifyJobs feed")
    scan_p.add_argument("--min-score", type=int, default=50, help="Minimum quality score (default 50)")
    scan_p.set_defaults(func=cmd_scan)

    # list
    list_p = sub.add_parser("list", help="List saved jobs")
    list_p.add_argument("--status", choices=["new", "applied", "skip"], default=None)
    list_p.set_defaults(func=cmd_list)

    # apply
    apply_p = sub.add_parser("apply", help="Run resume builder for a saved job")
    apply_p.add_argument("job_id", help="Job ID from `list`")
    apply_p.add_argument("--no-compile", action="store_true")
    apply_p.add_argument("--no-cover", action="store_true")
    apply_p.set_defaults(func=cmd_apply)

    # daemon
    daemon_p = sub.add_parser("daemon", help="Run continuous scan + auto-email loop")
    daemon_p.set_defaults(func=cmd_daemon)

    # dashboard
    dash_p = sub.add_parser("dashboard", help="Open web dashboard at localhost:8765")
    dash_p.add_argument("--port", type=int, default=8765)
    dash_p.set_defaults(func=cmd_dashboard)

    # seed
    seed_p = sub.add_parser("seed", help="Re-seed the knowledge graph")
    seed_p.set_defaults(func=cmd_seed)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()

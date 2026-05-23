"""
Main scanner orchestrator.
Runs all sources concurrently, quality-gates, deduplicates, and saves.
"""
from __future__ import annotations
import asyncio
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table
from rich import box

from .sources.ats import scrape_greenhouse, scrape_lever, scrape_ashby, scrape_workable
from .sources.aggregators import scrape_remoteok, scrape_remotive, scrape_jobicy
from .sources.hn import scrape_hn_hiring, scrape_hn_search
from .sources.simplify import scrape_simplify
from .quality import filter_jobs
from .store import save_jobs, list_jobs, stats

console = Console()

# Default ATS watchlist — verified working slugs
DEFAULT_ATS: list[tuple[str, str]] = [
    # Greenhouse
    ("greenhouse", "anthropic"),
    ("greenhouse", "scaleai"),
    ("greenhouse", "vercel"),
    ("greenhouse", "figma"),
    ("greenhouse", "cohere-3"),
    ("greenhouse", "notion"),
    # Lever
    ("lever", "huggingface"),
    ("lever", "anyscale"),
    ("lever", "together"),
    ("lever", "mistral-ai"),
    # Ashby
    ("ashby", "linear"),
    ("ashby", "cursor"),
    ("ashby", "replit"),
    ("ashby", "modal"),
]


async def _run_ats(provider: str, slug: str) -> list[dict]:
    scrapers = {
        "greenhouse": scrape_greenhouse,
        "lever": scrape_lever,
        "ashby": scrape_ashby,
        "workable": scrape_workable,
    }
    fn = scrapers.get(provider)
    if not fn:
        return []
    try:
        return await fn(slug)
    except Exception as e:
        console.print(f"[dim]  ⚠ {provider}/{slug}: {e}[/dim]")
        return []


async def run_scan(
    roles: list[str],
    remote_only: bool = True,
    ats_watchlist: list[tuple[str, str]] | None = None,
    include_aggregators: bool = True,
    include_hn: bool = True,
    include_simplify: bool = True,
    min_score: int = 50,
) -> dict:
    watchlist = ats_watchlist if ats_watchlist is not None else DEFAULT_ATS

    all_raw: list[dict] = []

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
        transient=True,
    ) as progress:
        # ATS sources
        if watchlist:
            task = progress.add_task(f"Scanning {len(watchlist)} company career pages...", total=None)
            ats_tasks = [_run_ats(p, s) for p, s in watchlist]
            ats_results = await asyncio.gather(*ats_tasks, return_exceptions=True)
            for r in ats_results:
                if isinstance(r, list):
                    all_raw.extend(r)
            progress.remove_task(task)

        # Aggregators
        if include_aggregators:
            task = progress.add_task("Scanning RemoteOK, Remotive, Jobicy...", total=None)
            agg_results = await asyncio.gather(
                scrape_remoteok(roles),
                scrape_remotive(roles),
                scrape_jobicy(roles),
                return_exceptions=True,
            )
            for r in agg_results:
                if isinstance(r, list):
                    all_raw.extend(r)
            progress.remove_task(task)

        # SimplifyJobs new-grad feed
        if include_simplify:
            task = progress.add_task("Scanning SimplifyJobs new-grad feed...", total=None)
            try:
                simplify_jobs = await scrape_simplify(roles)
                all_raw.extend(simplify_jobs)
            except Exception as e:
                console.print(f"[dim]  ⚠ simplify: {e}[/dim]")
            progress.remove_task(task)

        # HN
        if include_hn:
            task = progress.add_task("Scanning HN Who's Hiring...", total=None)
            hn_results = await asyncio.gather(
                scrape_hn_hiring(roles),
                *[scrape_hn_search(r) for r in roles[:3]],
                return_exceptions=True,
            )
            for r in hn_results:
                if isinstance(r, list):
                    all_raw.extend(r)
            progress.remove_task(task)

    # Quality gate + dedup by URL
    seen_urls: set[str] = set()
    deduped = []
    for j in all_raw:
        url = j.get("url", "")
        if url and url not in seen_urls:
            seen_urls.add(url)
            deduped.append(j)

    filtered = filter_jobs(deduped, roles, remote_only, min_score)
    inserted, dupes = save_jobs(filtered)

    return {
        "raw": len(all_raw),
        "after_dedup": len(deduped),
        "after_filter": len(filtered),
        "inserted": inserted,
        "dupes": dupes,
        "jobs": filtered,
    }


def print_results(result: dict) -> None:
    jobs = result["jobs"]
    console.print(f"\n[bold]Scan complete[/bold] — {result['raw']} raw → "
                  f"{result['after_dedup']} deduped → "
                  f"[green]{result['after_filter']} passed quality gate[/green] → "
                  f"[cyan]{result['inserted']} new saved[/cyan] "
                  f"([dim]{result['dupes']} dupes[/dim])\n")

    if not jobs:
        console.print("[yellow]No jobs passed the quality gate.[/yellow]")
        return

    table = Table(box=box.SIMPLE_HEAD, show_lines=False)
    table.add_column("Score", style="cyan", width=6)
    table.add_column("Title", style="bold", max_width=40)
    table.add_column("Company", max_width=20)
    table.add_column("Platform", style="dim", width=12)
    table.add_column("Location", max_width=16)
    table.add_column("Salary", style="green", max_width=18)

    for j in jobs[:30]:
        table.add_row(
            str(j.get("score", "")),
            j.get("title", "")[:40],
            j.get("company", "")[:20],
            j.get("platform", ""),
            j.get("location", "")[:16],
            j.get("salary", "")[:18],
        )

    console.print(table)
    if len(jobs) > 30:
        console.print(f"[dim]... and {len(jobs) - 30} more. Run `list` to see all.[/dim]")


def print_job_list(status: str | None = None) -> None:
    jobs = list_jobs(status=status, limit=100)
    if not jobs:
        console.print("[yellow]No jobs found.[/yellow]")
        return

    table = Table(box=box.SIMPLE_HEAD)
    table.add_column("ID", style="dim", width=10)
    table.add_column("Score", style="cyan", width=6)
    table.add_column("Status", width=8)
    table.add_column("Title", style="bold", max_width=38)
    table.add_column("Company", max_width=20)
    table.add_column("Platform", style="dim", width=12)
    table.add_column("Location", max_width=14)

    for j in jobs:
        status_style = {"new": "green", "applied": "blue", "skip": "dim"}.get(j["status"], "")
        table.add_row(
            j["id"],
            str(j["score"]),
            f"[{status_style}]{j['status']}[/{status_style}]",
            j["title"][:38],
            j["company"][:20],
            j["platform"],
            j.get("location", "")[:14],
        )

    console.print(table)
    s = stats()
    console.print(f"\n[dim]Total: {s['total']} | by status: {s['by_status']}[/dim]")

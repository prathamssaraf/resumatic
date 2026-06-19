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
from .sources.aggregators import (
    scrape_remoteok, scrape_remotive, scrape_jobicy, scrape_themuse, scrape_himalayas,
)
from .sources.hn import scrape_hn_hiring, scrape_hn_search
from .sources.simplify import scrape_simplify
from .quality import evaluate_job, CRITERIA
from .store import save_jobs, list_jobs, stats

console = Console()

# Default ATS watchlist — verified working slugs
DEFAULT_ATS: list[tuple[str, str]] = [
    # ── AI Labs & Frontier Models ─────────────────────────────────────────────
    ("greenhouse", "anthropic"),
    ("greenhouse", "togetherai"),       # was lever/together (404)
    ("greenhouse", "xai"),              # xAI / Grok
    ("ashby", "openai"),
    ("ashby", "perplexity"),
    ("ashby", "cohere"),                # was greenhouse/cohere-3 (404)
    ("ashby", "cognition"),             # Devin / Cognition AI
    ("ashby", "runway"),                # Runway ML
    ("lever", "anyscale"),
    ("lever", "mistral"),               # was lever/mistral-ai (404)
    ("workable", "huggingface"),        # was lever/huggingface (404)

    # ── AI Infra & Tooling ────────────────────────────────────────────────────
    ("greenhouse", "scaleai"),
    ("greenhouse", "databricks"),
    ("ashby", "modal"),
    ("ashby", "pinecone"),
    ("ashby", "elevenlabs"),
    ("ashby", "weaviate"),              # vector DB
    ("ashby", "airbyte"),               # data integration

    # ── Dev Tools & Platforms ─────────────────────────────────────────────────
    ("greenhouse", "vercel"),
    ("greenhouse", "figma"),
    ("greenhouse", "webflow"),
    ("greenhouse", "temporal"),         # workflow orchestration
    ("greenhouse", "amplitude"),
    ("greenhouse", "mixpanel"),
    ("greenhouse", "airtable"),
    ("ashby", "linear"),
    ("ashby", "cursor"),
    ("ashby", "replit"),
    ("ashby", "notion"),                # was greenhouse/notion (404)
    ("ashby", "snowflake"),
    ("ashby", "ramp"),
    ("ashby", "confluent"),

    # ── High-Volume Engineering Employers ─────────────────────────────────────
    ("greenhouse", "cloudflare"),
    ("greenhouse", "stripe"),
    ("greenhouse", "datadog"),
    ("greenhouse", "mongodb"),
    ("greenhouse", "elastic"),
    ("greenhouse", "airbnb"),
    ("greenhouse", "brex"),
    ("greenhouse", "twilio"),
    ("greenhouse", "chime"),
    ("greenhouse", "mercury"),          # fintech
    ("greenhouse", "marqeta"),
    ("lever", "netflix"),
    ("lever", "palantir"),
    ("lever", "plaid"),

    # ── Consumer / fintech / marketplace (high early-career volume) ────────────
    ("greenhouse", "discord"),
    ("greenhouse", "robinhood"),
    ("greenhouse", "coinbase"),
    ("greenhouse", "gusto"),
    ("greenhouse", "samsara"),
    ("greenhouse", "instacart"),
    ("greenhouse", "affirm"),
    ("greenhouse", "gitlab"),
    ("greenhouse", "reddit"),
    ("greenhouse", "asana"),
    ("greenhouse", "dropbox"),
    ("greenhouse", "faire"),
    ("greenhouse", "lyft"),
    ("greenhouse", "sofi"),
    ("greenhouse", "squarespace"),
    ("greenhouse", "flexport"),
    ("greenhouse", "pinterest"),

    # ── More AI / agent startups (Ashby) ──────────────────────────────────────
    ("ashby", "vanta"),
    ("ashby", "watershed"),
    ("ashby", "sardine"),
    ("ashby", "baseten"),
    ("ashby", "mintlify"),
    ("ashby", "sierra"),
    ("ashby", "decagon"),
    ("ashby", "harvey"),
    ("ashby", "suno"),
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
    ats_watchlist: list[tuple[str, str]] | None = None,
    include_aggregators: bool = True,
    include_hn: bool = True,
    include_simplify: bool = True,
    max_concurrent: int = 3,
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
            task = progress.add_task("Scanning RemoteOK, Remotive, Jobicy, The Muse, Himalayas...", total=None)
            agg_results = await asyncio.gather(
                scrape_remoteok(roles),
                scrape_remotive(roles),
                scrape_jobicy(roles),
                scrape_themuse(roles),
                scrape_himalayas(roles),
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

    # ── Free gates (no LLM): dedup by URL, drop no-URL/stale, drop known ──────
    # These are mechanical de-noising so Gemma only ever evaluates fresh, unseen
    # postings — never the same ~1000+ jobs every cycle.
    from .store import existing_job_ids, job_id as _job_id
    from .sources.common import is_recent

    seen_urls: set[str] = set()
    deduped = []
    for j in all_raw:
        url = j.get("url", "")
        if url and url not in seen_urls:
            seen_urls.add(url)
            deduped.append(j)

    known = existing_job_ids()
    candidates = [
        j for j in deduped
        if is_recent(j.get("posted_date", "")) and _job_id(j) not in known
    ]

    # ── LLM screen: each job is checked against every criterion, one call per ─
    # criterion, short-circuiting on the first failure. Jobs that pass all are
    # Approved and scored. Each verdict is SAVED IMMEDIATELY (approved or
    # rejected) so the dashboard fills live and a restart never re-screens work
    # already done. Bounded concurrency keeps the local model responsive.
    loop = asyncio.get_running_loop()
    sem = asyncio.Semaphore(max_concurrent)
    save_lock = asyncio.Lock()
    n_total = len(candidates)
    counts = {"approved": 0, "rejected": 0, "errored": 0, "inserted": 0, "dupes": 0, "done": 0}
    approved_jobs: list[dict] = []

    if n_total:
        console.print(f"  [cyan]Screening {n_total} fresh job(s) through {len(CRITERIA)} criteria…[/cyan]")

    async def _screen(job: dict) -> None:
        async with sem:
            try:
                verdict = await loop.run_in_executor(None, evaluate_job, job)
            except Exception as e:
                counts["errored"] += 1
                counts["done"] += 1
                console.print(f"  [dim]✗ screen error ({counts['done']}/{n_total}): {str(e)[:60]}[/dim]")
                return

        job["score"]        = verdict["score"]
        job["score_reason"] = verdict["reason"]
        job["status"]       = "approved" if verdict["approved"] else "rejected"

        async with save_lock:
            ins, dup = await loop.run_in_executor(None, save_jobs, [job])
        counts["inserted"] += ins
        counts["dupes"]    += dup
        counts["done"]     += 1
        if verdict["approved"]:
            counts["approved"] += 1
            approved_jobs.append(job)
            console.print(
                f"  [green]✓ APPROVED[/green] [dim]({counts['done']}/{n_total})[/dim] "
                f"{job.get('company','')[:18]} — {job['title'][:42]} "
                f"[dim](fit {verdict['score']})[/dim]"
            )
        else:
            counts["rejected"] += 1
            console.print(
                f"  [dim]· rejected ({counts['done']}/{n_total}) "
                f"{job.get('company','')[:18]} — {job['title'][:42]} "
                f"[{verdict.get('failed','')}][/dim]"
            )

    await asyncio.gather(*[_screen(j) for j in candidates])

    approved_n, rejected_n = counts["approved"], counts["rejected"]
    inserted, dupes, errored = counts["inserted"], counts["dupes"], counts["errored"]

    if errored:
        console.print(f"  [dim]{errored} job(s) errored during screening — will retry next cycle[/dim]")

    return {
        "raw": len(all_raw),
        "after_dedup": len(deduped),
        "candidates": len(candidates),
        "approved": approved_n,
        "rejected": rejected_n,
        "errored": errored,
        "inserted": inserted,
        "dupes": dupes,
        "jobs": approved_jobs,
    }


def print_results(result: dict) -> None:
    jobs = result["jobs"]
    console.print(f"\n[bold]Scan complete[/bold] — {result['raw']} raw → "
                  f"{result['after_dedup']} deduped → "
                  f"[cyan]{result['candidates']} screened by LLM[/cyan] → "
                  f"[green]{result['approved']} approved[/green], "
                  f"[dim]{result['rejected']} rejected[/dim] "
                  f"([dim]{result['inserted']} new saved[/dim])\n")

    if not jobs:
        console.print("[yellow]No jobs approved this scan.[/yellow]")
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
        status_style = {"approved": "green", "applied": "blue",
                        "rejected": "dim", "skip": "dim"}.get(j["status"], "")
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

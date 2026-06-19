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
from .quality import filter_jobs, llm_fit_check
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

    # ── Drop jobs already in the DB BEFORE any LLM work ──────────────────────
    # Without this, every scan re-fit-checks the same ~1000+ known jobs each
    # cycle, flooding the LLM and starving the build loop.
    from .store import existing_job_ids, job_id as _job_id
    known = existing_job_ids()
    fresh = [j for j in filtered if _job_id(j) not in known]

    # ── LLM fit-check for fresh high-score jobs only ─────────────────────────
    # Regex already killed the obvious ones; the LLM catches subtle mismatches
    # (implicit seniority, role-type mismatches). Concurrency is bounded so it
    # never saturates the thread pool the build loop also needs.
    import config as _cfg
    high = [j for j in fresh if j["score"] >= _cfg.MIN_SCORE_GOOD]
    low  = [j for j in fresh if j["score"] <  _cfg.MIN_SCORE_GOOD]

    to_save = low
    if high:
        loop = asyncio.get_running_loop()
        sem = asyncio.Semaphore(4)  # cap concurrent LLM calls

        async def _check(job: dict):
            async with sem:
                return await loop.run_in_executor(
                    None, llm_fit_check, job["title"], job.get("description", "")
                )

        checks = await asyncio.gather(*[_check(j) for j in high])
        passed, llm_rejected = [], []
        for job, (reject, reason) in zip(high, checks):
            if reject:
                llm_rejected.append((job["title"], job.get("company", ""), reason))
            else:
                passed.append(job)

        if llm_rejected:
            console.print(f"  [dim]LLM fit-check rejected {len(llm_rejected)} new high-score job(s):[/dim]")
            for title, company, reason in llm_rejected:
                console.print(f"    [dim]✗ {company} — {title[:45]} ({reason})[/dim]")

        to_save = passed + low

    filtered = to_save
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

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
from .sources.vanshb03 import scrape_vanshb03
from .sources.zapply import scrape_zapply
from .sources.citi import scrape_citi
from .sources.workday import scrape_workday
from .sources.amazon import scrape_amazon
from .sources.netflix import scrape_netflix
from .sources.google import scrape_google
from .sources.apple import scrape_apple
from .sources.meta import scrape_meta
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

    # ── Batch 3: more verified boards ─────────────────────────────────────────
    # Consumer / gaming / fintech / infra (Greenhouse)
    ("greenhouse", "verkada"),
    ("greenhouse", "toast"),
    ("greenhouse", "roblox"),
    ("greenhouse", "epicgames"),
    ("greenhouse", "postman"),
    ("greenhouse", "fivetran"),
    ("greenhouse", "nuro"),
    ("greenhouse", "duolingo"),
    ("greenhouse", "peloton"),
    ("greenhouse", "carta"),
    ("greenhouse", "attentive"),
    ("greenhouse", "gemini"),
    ("greenhouse", "doximity"),
    ("greenhouse", "planetscale"),
    ("greenhouse", "coursera"),
    ("greenhouse", "udemy"),
    # AI / agents / dev tools (Ashby)
    ("ashby", "crusoe"),
    ("ashby", "langchain"),
    ("ashby", "lovable"),
    ("ashby", "abridge"),
    ("ashby", "writer"),
    ("ashby", "rilla"),
    ("ashby", "physicalintelligence"),
    ("ashby", "distyl"),
    ("ashby", "zapier"),
    ("ashby", "character"),
    ("ashby", "openevidence"),
    ("ashby", "llamaindex"),
    ("ashby", "railway"),
    ("ashby", "browserbase"),
    ("ashby", "tldraw"),
    # Defense / consumer (Lever)
    ("lever", "shieldai"),
    ("lever", "spotify"),

    # ── Batch 4: enterprise SaaS / infra / more AI ────────────────────────────
    ("greenhouse", "okta"),
    ("greenhouse", "block"),
    ("greenhouse", "clickhouse"),
    ("greenhouse", "intercom"),
    ("greenhouse", "grafanalabs"),
    ("greenhouse", "hightouch"),
    ("greenhouse", "twitch"),
    ("greenhouse", "pagerduty"),
    ("greenhouse", "cockroachlabs"),
    ("greenhouse", "calendly"),
    ("ashby", "deepgram"),
    ("ashby", "mercor"),
    ("ashby", "supabase"),
    ("ashby", "speak"),
    ("ashby", "cartesia"),
    ("ashby", "warp"),
    ("ashby", "granola"),
    ("ashby", "neon"),
    ("ashby", "pika"),
    ("lever", "veeva"),

    # ── Batch 5: security, crypto/fintech, defense, data, more AI ──────────────
    # Greenhouse
    ("greenhouse", "ripple"),
    ("greenhouse", "helsing"),
    ("greenhouse", "newrelic"),
    ("greenhouse", "fireblocks"),
    ("greenhouse", "abnormalsecurity"),
    ("greenhouse", "tanium"),
    ("greenhouse", "huntress"),
    ("greenhouse", "betterment"),
    ("greenhouse", "life360"),
    ("greenhouse", "vannevarlabs"),
    ("greenhouse", "sumologic"),
    ("greenhouse", "nextdoor"),
    ("greenhouse", "starburst"),
    ("greenhouse", "dremio"),
    ("greenhouse", "imbue"),
    # Ashby (AI model / media labs + infra)
    ("ashby", "fireworksai"),
    ("ashby", "lambda"),
    ("ashby", "poolside"),
    ("ashby", "reka"),
    ("ashby", "sesame"),
    ("ashby", "krea"),
    ("ashby", "photoroom"),
    ("ashby", "tavus"),
    ("ashby", "ideogram"),
    ("ashby", "hedra"),
    ("ashby", "recraft"),
    ("ashby", "viggle"),
    ("ashby", "dust"),
    ("ashby", "motherduck"),
    ("ashby", "zed"),
    # Lever
    ("lever", "tala"),

    # ── Batch 6: major high-volume employers ──────────────────────────────────
    ("greenhouse", "zscaler"),
    ("greenhouse", "purestorage"),
    ("greenhouse", "lucidmotors"),
    ("greenhouse", "braze"),
    ("greenhouse", "klaviyo"),
    ("greenhouse", "riotgames"),
    ("greenhouse", "rubrik"),
    ("greenhouse", "fastly"),
    ("greenhouse", "instabase"),
    ("ashby", "saronic"),
    ("ashby", "flock"),
    ("ashby", "commure"),
    ("greenhouse", "atricure"),
]


# Hard wall-clock cap per source. Without this, a single slow/hanging source
# (e.g. a Cloudflare-fronted board that trickles bytes so the read timeout never
# fires) stalls the entire scan cycle and it never reaches screening.
_SOURCE_TIMEOUT = 45


async def _guard(coro, name: str, timeout: int = _SOURCE_TIMEOUT) -> list[dict]:
    """Run a scraper coroutine with a hard timeout; return [] on timeout/error."""
    try:
        return await asyncio.wait_for(coro, timeout)
    except asyncio.TimeoutError:
        console.print(f"[dim]  ⚠ {name}: timed out after {timeout}s[/dim]")
        return []
    except Exception as e:
        console.print(f"[dim]  ⚠ {name}: {e}[/dim]")
        return []


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
    return await _guard(fn(slug), f"{provider}/{slug}")


async def run_scan(
    roles: list[str],
    ats_watchlist: list[tuple[str, str]] | None = None,
    include_aggregators: bool = True,
    include_hn: bool = True,
    include_simplify: bool = True,
    include_vanshb03: bool = True,
    include_zapply: bool = True,
    include_citi: bool = True,
    include_workday: bool = True,
    include_bigtech: bool = True,
    include_meta: bool = True,
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
                _guard(scrape_remoteok(roles), "remoteok"),
                _guard(scrape_remotive(roles), "remotive"),
                _guard(scrape_jobicy(roles), "jobicy"),
                _guard(scrape_themuse(roles), "themuse"),
                _guard(scrape_himalayas(roles), "himalayas"),
                return_exceptions=True,
            )
            for r in agg_results:
                if isinstance(r, list):
                    all_raw.extend(r)
            progress.remove_task(task)

        # SimplifyJobs new-grad feed
        if include_simplify:
            task = progress.add_task("Scanning SimplifyJobs new-grad feed...", total=None)
            all_raw.extend(await _guard(scrape_simplify(roles), "simplify"))
            progress.remove_task(task)

        # vanshb03/New-Grad-2026 — same listings.json format, different bot/curation
        if include_vanshb03:
            task = progress.add_task("Scanning vanshb03 new-grad feed...", total=None)
            all_raw.extend(await _guard(scrape_vanshb03(roles), "vanshb03"))
            progress.remove_task(task)

        # zapplyjobs README table — 500 rows, refreshed every 15 min upstream
        if include_zapply:
            task = progress.add_task("Scanning zapplyjobs new-grad SWE feed...", total=None)
            all_raw.extend(await _guard(scrape_zapply(roles), "zapply", timeout=180))
            progress.remove_task(task)

        # Citi — every US posting from the last 2 months (fetches per-job detail
        # pages; big first-cycle backfill, cheap after via URL dedup).
        if include_citi:
            task = progress.add_task("Scanning Citi (US, last 2 months)...", total=None)
            all_raw.extend(await _guard(scrape_citi(roles), "citi", timeout=900))
            progress.remove_task(task)

        # Workday — major employers (NVIDIA, Salesforce, Wells Fargo, …) via CXS API
        if include_workday:
            task = progress.add_task("Scanning Workday employers...", total=None)
            all_raw.extend(await _guard(scrape_workday(roles), "workday", timeout=300))
            progress.remove_task(task)

        # Big tech with plain-HTTP job APIs (no browser needed) — Amazon, Netflix,
        # Google, Apple. (Meta needs a real browser and runs separately via `main.py meta`.)
        if include_bigtech:
            task = progress.add_task("Scanning Amazon, Netflix, Google, Apple...", total=None)
            bigtech_results = await asyncio.gather(
                _guard(scrape_amazon(roles), "amazon", timeout=300),
                _guard(scrape_netflix(roles), "netflix", timeout=180),
                _guard(scrape_google(roles), "google", timeout=180),
                _guard(scrape_apple(roles), "apple", timeout=300),
                return_exceptions=True,
            )
            for r in bigtech_results:
                if isinstance(r, list):
                    all_raw.extend(r)
            progress.remove_task(task)

        # Meta — browser-driven (Playwright), capped per cycle so a 20-min scan
        # keeps moving; URL dedup means each cycle just picks up new postings.
        if include_meta:
            task = progress.add_task("Scanning Meta (browser)...", total=None)
            all_raw.extend(await _guard(scrape_meta(max_detail=40), "meta", timeout=600))
            progress.remove_task(task)

        # HN
        if include_hn:
            task = progress.add_task("Scanning HN Who's Hiring...", total=None)
            hn_results = await asyncio.gather(
                _guard(scrape_hn_hiring(roles), "hn-hiring"),
                *[_guard(scrape_hn_search(r), "hn-search") for r in roles[:3]],
                return_exceptions=True,
            )
            for r in hn_results:
                if isinstance(r, list):
                    all_raw.extend(r)
            progress.remove_task(task)

    # ── Free gates (no LLM): dedup by URL, drop no-URL/stale, drop known ──────
    # These are mechanical de-noising so Gemma only ever evaluates fresh, unseen
    # postings — never the same ~1000+ jobs every cycle.
    from .store import existing_job_ids, existing_urls, job_id as _job_id
    from .sources.common import is_recent

    seen_urls: set[str] = set()
    deduped = []
    for j in all_raw:
        url = j.get("url", "")
        if url and url not in seen_urls:
            seen_urls.add(url)
            deduped.append(j)

    known = existing_job_ids()
    known_urls = existing_urls()
    # Exclude anything already stored by BOTH keys: id = md5(company|title) AND the
    # UNIQUE url. Filtering only by id let title/company drift smuggle a job past
    # the gate, where it then bounced on the url constraint and got re-screened
    # every cycle forever (burning the whole LLM budget on uncommittable dupes).
    # Citi/Workday apply their own recency + US filtering in the scraper and tag
    # non-US/stale ones with screen_skip_reason, so exempt them from the 7-day gate.
    candidates = [
        j for j in deduped
        if (is_recent(j.get("posted_date", "")) or j.get("platform") in ("citi", "workday"))
        and _job_id(j) not in known
        and j.get("url", "") not in known_urls
    ]

    # Pre-screen skips: Citi postings already judged non-US / older than 2 months
    # at scrape time. Save them as 'skip' (no LLM) so their URL is recorded once
    # and never re-fetched — they are hidden from the dashboard's Rejected view.
    prescreen_skips = [j for j in candidates if j.get("screen_skip_reason")]
    candidates = [j for j in candidates if not j.get("screen_skip_reason")]
    if prescreen_skips:
        for j in prescreen_skips:
            j["status"] = "skip"
            j["score"] = 0
            j["score_reason"] = j["screen_skip_reason"]
        save_jobs(prescreen_skips)

    # ── LLM screen: each job is checked against every criterion, one call per ─
    # criterion, short-circuiting on the first failure. Jobs that pass all are
    # Approved and scored. Each verdict is SAVED IMMEDIATELY (approved or
    # rejected) so the dashboard fills live and a restart never re-screens work
    # already done. Bounded concurrency keeps the local model responsive.
    screened = await screen_and_save(candidates, max_concurrent=max_concurrent)

    return {
        "raw": len(all_raw),
        "after_dedup": len(deduped),
        "candidates": len(candidates),
        **screened,
    }


async def screen_and_save(candidates: list[dict], max_concurrent: int = 3) -> dict:
    """Run the LLM screen over `candidates` and save each verdict immediately.
    Shared by run_scan() and any other source (e.g. LinkedIn) that needs to feed
    the same Approved/Rejected pipeline on its own schedule."""
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

    if counts["errored"]:
        console.print(f"  [dim]{counts['errored']} job(s) errored during screening — will retry next cycle[/dim]")

    return {
        "approved": counts["approved"],
        "rejected": counts["rejected"],
        "errored": counts["errored"],
        "inserted": counts["inserted"],
        "dupes": counts["dupes"],
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

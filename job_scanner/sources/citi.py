"""
Citi careers — Radancy / TalentBrew (jobs.citi.com).

Scans EVERY Citi US posting from the last ~2 months and screens each with the
two-gate Citi rules (see job_scanner.quality.CITI_CRITERIA). There is no reliable
server-side US/date facet, so US-ness and the posting date come from each job's
JSON-LD JobPosting block on its detail page.

To keep this affordable the listing pages are enumerated concurrently, and a
detail page is fetched only for a URL not already in the DB. Jobs that turn out
non-US or older than the window are returned tagged with `screen_skip_reason` so
the scanner records them as 'skip' — that way each URL is fetched exactly once
(no re-fetching thousands of non-US pages every cycle) and no LLM time is wasted.

Citi jobs are tagged platform="citi".
"""
from __future__ import annotations
import asyncio
import html
import json
import os
import re
from datetime import datetime, timedelta, timezone

from .common import text_get, parse_date

BASE = "https://jobs.citi.com"
RECENT_DAYS = 60  # "past 2 months"
# Citi hard-blocks (403) our home IP after the backfill. Route Citi (only) through
# a proxy if CITI_PROXY is set (e.g. socks5://127.0.0.1:9050 for local Tor).
_PROXY = os.environ.get("CITI_PROXY") or None
# Citi's WAF hard-blocks (403) bursty scraping. Stay polite: a real browser
# header set, low concurrency, and per-cycle caps so the big backfill is spread
# over many cycles instead of hammering the site in one shot.
_UA = {
    "User-Agent": ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                   "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://jobs.citi.com/",
}
_US_COUNTRIES = {"united states", "united states of america", "usa", "us"}
_LD = re.compile(r'type="application/ld\+json"[^>]*>(.*?)</script>', re.DOTALL)
_HREF = re.compile(r'href="(/job/[^"]+)"')
_PAGES_PER_CYCLE = 60      # enumerate at most this many listing pages per scan (~900 jobs)
_MAX_NEW_PER_CYCLE = 80    # fetch at most this many new detail pages per scan
_REQ_DELAY = 0.25          # polite delay between requests (seconds)


def _parse_job(doc: str, href: str, cutoff: str) -> dict | None:
    """Parse a Citi detail page's JSON-LD. Returns a job dict, tagging non-US or
    stale postings with screen_skip_reason. None only if unparseable."""
    m = _LD.search(doc)
    if not m:
        return None
    try:
        d = json.loads(m.group(1).strip())
    except json.JSONDecodeError:
        return None
    if d.get("@type") != "JobPosting":
        return None

    locs = d.get("jobLocation") or []
    if isinstance(locs, dict):
        locs = [locs]
    addr = (locs[0].get("address") if locs else {}) or {}
    country = str(addr.get("addressCountry", "")).strip().lower()
    city = addr.get("addressLocality", "")
    region = addr.get("addressRegion", "")
    location = ", ".join(x for x in (city, region) if x) or (addr.get("addressCountry") or "")

    desc = re.sub(r"<[^>]+>", " ", d.get("description", "") or "")
    desc = html.unescape(re.sub(r"\s+", " ", desc)).strip()
    posted = parse_date(d.get("datePosted", ""))

    # Structured pay (US pay-transparency postings carry baseSalary MonetaryAmount)
    salary = ""
    bs = d.get("baseSalary") or {}
    val = bs.get("value") if isinstance(bs, dict) else None
    if isinstance(val, dict):
        lo, hi = val.get("minValue"), val.get("maxValue")
        unit = (val.get("unitText") or "").lower()
        cur = bs.get("currency", "USD")
        if lo or hi:
            rng = f"{lo}-{hi}" if lo and hi and lo != hi else f"{lo or hi}"
            salary = f"{cur} {rng}/{unit or 'year'}"

    job = {
        "title": d.get("title", ""),
        "company": "Citi",
        "url": BASE + href,
        "platform": "citi",
        "description": desc[:100000],
        "location": location or "United States",
        "salary": salary,
        "posted_date": posted,
    }
    if country not in _US_COUNTRIES:
        job["screen_skip_reason"] = f"non-US ({addr.get('addressCountry', '?')})"
    elif posted and posted[:10] < cutoff:
        job["screen_skip_reason"] = "older than 2 months"
    return job


async def _all_hrefs(concurrency: int) -> list[str]:
    """Enumerate every /job/ href across the full listing (pages fetched concurrently)."""
    first = await text_get(f"{BASE}/search-jobs?p=1", headers=_UA, proxy=_PROXY)
    if not first:
        return []
    m = re.search(r"([\d,]+)\s+Results", first)
    total = int(m.group(1).replace(",", "")) if m else 15
    num_pages = min(_PAGES_PER_CYCLE, total // 15 + 2)

    sem = asyncio.Semaphore(concurrency)

    async def _page(pg: int) -> list[str]:
        if pg == 1:
            return _HREF.findall(first)
        async with sem:
            doc = await text_get(f"{BASE}/search-jobs?p={pg}", headers=_UA, proxy=_PROXY)
            await asyncio.sleep(_REQ_DELAY)
        return _HREF.findall(doc)

    pages = await asyncio.gather(*[_page(pg) for pg in range(1, num_pages + 1)],
                                 return_exceptions=True)
    out: list[str] = []
    seen: set[str] = set()
    for p in pages:
        if isinstance(p, list):
            for h in p:
                if h not in seen:
                    seen.add(h)
                    out.append(h)
    return out


async def scrape_citi(roles: list[str] | None = None, concurrency: int = 3) -> list[dict]:
    from job_scanner.store import existing_urls
    known = existing_urls()

    hrefs = await _all_hrefs(concurrency)
    # Fetch each URL only once, ever, and cap per cycle so the backfill spreads
    # over many scans rather than hammering Citi (which 403-blocks bursts).
    new = [h for h in hrefs if (BASE + h) not in known][:_MAX_NEW_PER_CYCLE]
    if not new:
        return []

    cutoff = (datetime.now(tz=timezone.utc) - timedelta(days=RECENT_DAYS)).strftime("%Y-%m-%d")
    sem = asyncio.Semaphore(concurrency)

    async def _detail(href: str) -> dict | None:
        async with sem:
            doc = await text_get(BASE + href, headers=_UA, proxy=_PROXY)
            await asyncio.sleep(_REQ_DELAY)
        return _parse_job(doc, href, cutoff) if doc else None

    parsed = await asyncio.gather(*[_detail(h) for h in new], return_exceptions=True)
    jobs = [p for p in parsed if isinstance(p, dict)]
    jobs.sort(key=lambda j: j.get("posted_date", ""), reverse=True)  # newest first
    return jobs

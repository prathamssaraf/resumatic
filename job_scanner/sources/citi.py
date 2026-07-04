"""
Citi careers — Radancy / TalentBrew (jobs.citi.com).

Scrapes the "Student and Grad Programs" career-level facet, keeps US-only
postings (via JSON-LD addressCountry), and returns them newest-first. Each job's
detail page carries a JSON-LD JobPosting block with title, datePosted, location,
and full description.

Citi jobs are tagged platform="citi" so the screener applies a wider role gate
(tech / IB analyst / anything open to a tech degree) — see job_scanner.quality.
"""
from __future__ import annotations
import asyncio
import html
import json
import re
from urllib.parse import urlencode

from .common import text_get, parse_date

BASE = "https://jobs.citi.com"
_GRAD_FACET = '[{"key":"custom_fields.CFCareerLevel","value":"Student and Grad Programs"}]'
_US_COUNTRIES = {"united states", "united states of america", "usa", "us"}
_LD = re.compile(r'type="application/ld\+json"[^>]*>(.*?)</script>', re.DOTALL)


async def _job_hrefs(max_pages: int) -> list[str]:
    """Paginate the grad-programs listing and collect unique /job/ hrefs."""
    hrefs: list[str] = []
    seen: set[str] = set()
    for pg in range(1, max_pages + 1):
        q = urlencode({"ascf": _GRAD_FACET, "p": pg})
        doc = await text_get(f"{BASE}/search-jobs?{q}")
        found = [h for h in re.findall(r'href="(/job/[^"]+)"', doc) if h not in seen]
        if not found:
            break
        for h in found:
            seen.add(h)
        hrefs.extend(found)
    return hrefs


def _parse_job(doc: str, href: str) -> dict | None:
    """Parse a Citi job detail page's JSON-LD. Returns None if non-US or unparseable."""
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
    if str(addr.get("addressCountry", "")).strip().lower() not in _US_COUNTRIES:
        return None  # US only

    city = addr.get("addressLocality", "")
    region = addr.get("addressRegion", "")
    location = ", ".join(x for x in (city, region) if x) or "United States"

    desc = re.sub(r"<[^>]+>", " ", d.get("description", "") or "")
    desc = html.unescape(re.sub(r"\s+", " ", desc)).strip()

    return {
        "title": d.get("title", ""),
        "company": "Citi",
        "url": BASE + href,
        "platform": "citi",
        "description": desc[:100000],
        "location": location,
        "posted_date": parse_date(d.get("datePosted", "")),
    }


async def scrape_citi(roles: list[str] | None = None,
                      max_pages: int = 5, concurrency: int = 8) -> list[dict]:
    hrefs = await _job_hrefs(max_pages)
    if not hrefs:
        return []
    sem = asyncio.Semaphore(concurrency)

    async def _fetch(href: str) -> dict | None:
        async with sem:
            doc = await text_get(BASE + href)
        return _parse_job(doc, href) if doc else None

    results = await asyncio.gather(*[_fetch(h) for h in hrefs], return_exceptions=True)
    jobs = [r for r in results if isinstance(r, dict)]
    # No recency filter: grad/analyst programs are posted months ahead and stay
    # open far longer than the 7-day window used for regular listings.
    jobs.sort(key=lambda j: j.get("posted_date", ""), reverse=True)  # newest first
    return jobs

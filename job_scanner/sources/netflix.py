"""
Netflix careers (explore.jobs.netflix.net) — public JSON API, no browser needed.

The jobs LIST endpoint gives title/location/dates but an empty job_description;
the full description only appears on the per-job DETAIL endpoint, so we fetch
that for each new, unseen, US-plausible posting.
"""
from __future__ import annotations
import asyncio
import re

from .common import json_get, parse_date, is_recent

LIST_URL = "https://explore.jobs.netflix.net/api/apply/v2/jobs"
DETAIL_URL = "https://explore.jobs.netflix.net/api/apply/v2/jobs/{id}"
_UA = {"User-Agent": ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                      "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36")}
_PAGE = 100
_MAX_PAGES = 8            # ~800 postings enumerated per cycle
_MAX_DETAIL_PER_CYCLE = 60
_CONCURRENCY = 6

_US_HINT = re.compile(
    r",\s*(United States(?:\s+of\s+America)?|USA|US)\s*$|^USA\s*-\s*Remote", re.I)


def _is_us(loc: str) -> bool:
    return bool(_US_HINT.search(loc or ""))


async def scrape_netflix(roles: list[str] | None = None) -> list[dict]:
    from job_scanner.store import existing_urls
    known = existing_urls()

    candidates = []
    for pg in range(_MAX_PAGES):
        data = await json_get(LIST_URL, params={
            "domain": "netflix.com", "start": pg * _PAGE, "num": _PAGE, "sort_by": "new",
        }, headers=_UA)
        positions = (data or {}).get("positions", [])
        if not positions:
            break
        for p in positions:
            url = p.get("canonicalPositionUrl", "") or f"https://explore.jobs.netflix.net/careers/job/{p.get('id')}"
            if not url or url in known:
                continue
            posted = parse_date(p.get("t_create"))
            if not is_recent(posted):
                continue
            candidates.append({"id": p.get("id"), "url": url, "title": p.get("name", ""),
                               "location": p.get("location", "") or "", "posted_date": posted})
        if len(positions) < _PAGE:
            break
    candidates = candidates[:_MAX_DETAIL_PER_CYCLE]

    sem = asyncio.Semaphore(_CONCURRENCY)

    async def _detail(c: dict) -> dict:
        async with sem:
            d = await json_get(DETAIL_URL.format(id=c["id"]), params={"domain": "netflix.com"}, headers=_UA)
        desc = re.sub(r"<[^>]+>", " ", (d or {}).get("job_description", "") or "")
        desc = re.sub(r"\s+", " ", desc).strip()
        job = {
            "title": c["title"], "company": "Netflix", "url": c["url"], "platform": "netflix",
            "description": desc[:100000], "location": c["location"], "posted_date": c["posted_date"],
        }
        if not _is_us(c["location"]):
            job["screen_skip_reason"] = f"non-US ({c['location'][:40]})"
        return job

    results = await asyncio.gather(*[_detail(c) for c in candidates], return_exceptions=True)
    return [r for r in results if isinstance(r, dict)]

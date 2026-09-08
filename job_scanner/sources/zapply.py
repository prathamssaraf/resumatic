"""
zapplyjobs/New-Grad-Software-Engineering-Jobs-2027 — no JSON API, just a big
README markdown table (~500 rows across 5 role sections, refreshed every 15
min upstream). The table truncates title/location with "…", so for each row
we only trust company + the apply URL, then use fetch_ats_detail() to recover
the real title/description/location/posted_date from the ATS itself (mostly
Workday, also Greenhouse/Lever/Ashby — see job_scanner/sources/common.py).

No category/role-type pre-filter here on purpose — the table includes a
Program-Management section too, but the normal LLM role_type criterion
already rejects those, matching this project's "no regex/keyword filtering"
approach to role screening.
"""
from __future__ import annotations
import asyncio
import re

from .common import text_get, fetch_ats_detail, is_recent

README_URL = (
    "https://raw.githubusercontent.com/zapplyjobs/New-Grad-Software-Engineering-Jobs-2027"
    "/main/README.md"
)

_ROW_RE = re.compile(
    r'^\| \*\*(?P<company>[^*]+)\*\* \| (?P<title>[^|]+?) \| (?P<location>[^|]+?) \| '
    r'(?P<posted>[^|]+?) \| (?P<visa>[^|]*)\| \[.*?\]\((?P<url>[^)]+)\)',
    re.MULTILINE,
)

_MAX_DETAIL_PER_CYCLE = 100  # cap ATS detail fetches per scan — the README only ever
                             # holds ~500 rows total (freshest per section, refreshed
                             # upstream every 15 min), and existing_urls() dedup means
                             # only genuinely new rows reach this fetch each cycle.


async def scrape_zapply(roles: list[str] | None = None) -> list[dict]:
    from job_scanner.store import existing_urls

    doc = await text_get(README_URL)
    if not doc:
        return []

    known = existing_urls()
    rows = _ROW_RE.findall(doc)
    seen: set[str] = set()
    candidates = []
    for company, title, location, posted, visa, url in rows:
        url = url.strip()
        if not url or url in known or url in seen:
            continue
        seen.add(url)
        candidates.append({"company": company.strip(), "title": title.strip(),
                           "location": location.strip(), "url": url})
    candidates = candidates[:_MAX_DETAIL_PER_CYCLE]

    sem = asyncio.Semaphore(10)

    async def _fetch(c: dict) -> dict | None:
        async with sem:
            detail = await fetch_ats_detail(c["url"])
        title = detail.get("title") or c["title"]
        description = detail.get("description") or f"{title} at {c['company']}. Location: {c['location']}."
        location = detail.get("location") or c["location"]
        posted_date = detail.get("posted_date", "")
        job = {
            "title": title,
            "company": c["company"],
            "url": c["url"],
            "platform": "zapply",
            "description": description[:100000],
            "location": location,
            "posted_date": posted_date,
        }
        country = detail.get("country", "")
        if country and country not in ("united states", "united states of america", "usa", "us"):
            job["screen_skip_reason"] = f"non-US ({country})"
        elif posted_date and not is_recent(posted_date):
            return None  # stale — drop rather than re-screen every cycle
        return job

    results = await asyncio.gather(*[_fetch(c) for c in candidates], return_exceptions=True)
    return [r for r in results if isinstance(r, dict)]

"""
Google XR/AR/VR tracker — standalone, on-demand scraper for the dedicated
"Google XR" dashboard tab.

Deliberately independent of scanner.py / quality.py: no LLM screening, no
daemon wiring. Three deterministic checks only:
  1. New-grad / mid-level (title has no senior/staff/manager/director marker)
  2. US-based (via the same per-location country codes used in sources/google.py)
  3. XR / AR / VR related (matched via Google's own search relevance across
     several queries, merged and deduped)

Real posted dates come from the same AF_initDataCallback ds:0 blob used by
sources/google.py (job[12] = creation timestamp) — see that module for how
this was discovered/verified.
"""
from __future__ import annotations
import asyncio
import json
import re
from datetime import datetime, timezone

from .common import text_get

BASE = "https://www.google.com/about/careers/applications/jobs/results/"
_UA = {"User-Agent": ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                      "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36")}
_TITLE = re.compile(r'<h3 class="QJPWVe">([^<]+)</h3>')
_HREF = re.compile(r'jobs/results/(\d+-[a-z0-9\-]+)')
_AF_BLOCK = re.compile(r"AF_initDataCallback\((\{.*?\})\);\s*</script>", re.DOTALL)
_DATA = re.compile(r"data:(\[.*\]),\s*sideChannel", re.DOTALL)

_QUERIES = ["XR", "Augmented Reality", "Virtual Reality"]
_SENIOR_RE = re.compile(
    r"(?<!\w)(senior|sr\.?|staff|principal|distinguished|director|"
    r"vp|vice president|head of|manager|lead)(?!\w)", re.I)
_MAX_PAGES_PER_QUERY = 6      # ~120 listings/query enumerated
_MAX_DETAIL = 150             # cap detail fetches per run


async def _list_page(query: str, page_num: int) -> list[tuple[str, str]]:
    doc = await text_get(BASE, params={"q": query, "sort_by": "date", "page": page_num}, headers=_UA)
    if not doc:
        return []
    return list(zip(_TITLE.findall(doc), _HREF.findall(doc)))


def _parse_detail(doc: str) -> dict | None:
    blocks = _AF_BLOCK.findall(doc)
    ds0 = next((b for b in blocks if "key: 'ds:0'" in b), None)
    if not ds0:
        return None
    m = _DATA.search(ds0)
    if not m:
        return None
    try:
        job = json.loads(m.group(1))[0]
    except (json.JSONDecodeError, IndexError):
        return None

    locs = job[9] or []
    countries = {l[5] for l in locs if len(l) > 5 and l[5]}
    location = "; ".join(l[0] for l in locs) if locs else ""

    parts = []
    for idx in (10, 3, 4):  # full description, responsibilities, min quals
        field = job[idx] if idx < len(job) else None
        if field and isinstance(field, list) and field[1]:
            parts.append(re.sub(r"<[^>]+>", " ", field[1]))
    desc = re.sub(r"\s+", " ", " ".join(parts)).strip()

    ts = job[12][0] if len(job) > 12 and job[12] else None
    posted = datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d") if ts else ""

    return {"title": job[1], "location": location, "countries": countries,
            "description": desc, "posted_date": posted}


async def scrape_google_xr() -> list[dict]:
    """Independent XR/AR/VR scan: non-senior + US-only. Returns newest-first."""
    from job_scanner.xr_store import existing_xr_urls
    known = existing_xr_urls()

    seen_ids: set[str] = set()
    candidates: list[str] = []
    for q in _QUERIES:
        for pg in range(1, _MAX_PAGES_PER_QUERY + 1):
            items = await _list_page(q, pg)
            if not items:
                break
            new_this_page = 0
            for title, href in items:
                jid = href.split("-")[0]
                if jid in seen_ids:
                    continue
                seen_ids.add(jid)
                new_this_page += 1
                if _SENIOR_RE.search(title):
                    continue  # cheap pre-filter before spending a detail fetch
                url = BASE + href
                if url not in known:
                    candidates.append(url)
            if new_this_page == 0:
                break
    candidates = candidates[:_MAX_DETAIL]

    sem = asyncio.Semaphore(8)

    async def _fetch(url: str) -> dict | None:
        async with sem:
            doc = await text_get(url, headers=_UA)
        if not doc:
            return None
        parsed = _parse_detail(doc)
        if not parsed or not parsed["description"]:
            return None
        if _SENIOR_RE.search(parsed["title"]):
            return None
        if parsed["countries"] and "US" not in parsed["countries"]:
            return None
        return {
            "title": parsed["title"], "company": "Google", "url": url,
            "location": parsed["location"] or "United States",
            "posted_date": parsed["posted_date"], "description": parsed["description"][:100000],
        }

    results = await asyncio.gather(*[_fetch(u) for u in candidates], return_exceptions=True)
    jobs = [r for r in results if isinstance(r, dict)]
    jobs.sort(key=lambda j: j["posted_date"], reverse=True)
    return jobs

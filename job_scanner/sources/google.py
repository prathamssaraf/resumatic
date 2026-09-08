"""
Google careers (google.com/about/careers) — plain HTTP, no browser needed.

Google server-renders the job list into HTML (no JS/API call needed for the
list), but each posting's full description + clean per-location country codes
only live in a `AF_initDataCallback({key: 'ds:0', ...})` JSON blob embedded on
its own detail page, so we paginate the list, then fetch+parse that blob for
each new, unseen URL.

Google does not expose a real "posted date" in this data (the only timestamp
present is a page-render stamp, not the original posting date), so postings are
timestamped with the scrape date and rely on de-dup (existing_urls) rather than
a true recency filter — a known limitation vs. the other sources.
"""
from __future__ import annotations
import json
import re
from datetime import date

from .common import text_get

BASE = "https://www.google.com/about/careers/applications/jobs/results/"
_UA = {"User-Agent": ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                      "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36")}
_TITLE = re.compile(r'<h3 class="QJPWVe">([^<]+)</h3>')
_HREF = re.compile(r'jobs/results/(\d+-[a-z0-9\-]+)')
_AF_BLOCK = re.compile(r"AF_initDataCallback\((\{.*?\})\);\s*</script>", re.DOTALL)
_DATA = re.compile(r"data:(\[.*\]),\s*sideChannel", re.DOTALL)
_MAX_LIST_PAGES = 15     # ~300 postings enumerated per cycle
_MAX_DETAIL_PER_CYCLE = 60


async def _list_page(page_num: int) -> list[tuple[str, str]]:
    doc = await text_get(BASE, params={"sort_by": "date", "page": page_num}, headers=_UA)
    if not doc:
        return []
    return list(zip(_TITLE.findall(doc), _HREF.findall(doc)))


def _parse_detail(doc: str) -> dict | None:
    ds0 = None
    for block in _AF_BLOCK.findall(doc):
        if "key: 'ds:0'" in block:
            ds0 = block
            break
    if not ds0:
        return None
    dm = _DATA.search(ds0)
    if not dm:
        return None
    try:
        job = json.loads(dm.group(1))[0]
    except (json.JSONDecodeError, IndexError):
        return None

    locs = job[9] or []  # [[name, [addr], city, zip, state_code, country_code], ...]
    countries = {l[5] for l in locs if len(l) > 5 and l[5]}
    location = "; ".join(l[0] for l in locs) if locs else ""

    parts = []
    for idx in (10, 3, 4):  # full description, responsibilities, min quals
        field = job[idx] if idx < len(job) else None
        if field and isinstance(field, list) and field[1]:
            parts.append(re.sub(r"<[^>]+>", " ", field[1]))
    desc = re.sub(r"\s+", " ", " ".join(parts)).strip()
    if not desc:
        return None

    return {"title": job[1], "location": location, "countries": countries, "description": desc}


async def scrape_google(roles: list[str] | None = None) -> list[dict]:
    from job_scanner.store import existing_urls
    known = existing_urls()

    candidates: list[str] = []
    for pg in range(1, _MAX_LIST_PAGES + 1):
        items = await _list_page(pg)
        if not items:
            break
        for _title, href in items:
            url = BASE + href
            if url not in known and url not in candidates:
                candidates.append(url)
        if len(candidates) >= _MAX_DETAIL_PER_CYCLE:
            break
    candidates = candidates[:_MAX_DETAIL_PER_CYCLE]

    out = []
    today = date.today().isoformat()
    for url in candidates:
        doc = await text_get(url, headers=_UA)
        if not doc:
            continue
        parsed = _parse_detail(doc)
        if not parsed:
            continue

        job = {
            "title": parsed["title"],
            "company": "Google",
            "url": url,
            "platform": "google",
            "description": parsed["description"][:100000],
            "location": parsed["location"] or "Multiple",
            "posted_date": today,
        }
        if parsed["countries"] and "US" not in parsed["countries"]:
            job["screen_skip_reason"] = f"non-US ({', '.join(sorted(parsed['countries']))[:30]})"
        out.append(job)
    return out

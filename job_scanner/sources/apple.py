"""
Apple careers (jobs.apple.com) — plain HTTP, no browser needed.

Both the search-results page and each job's detail page are server-rendered:
- Search: a repeating HTML card per posting (title/href/date/location parsed
  via regex — no JSON endpoint exposes this; the site's own /api/v1/* routes
  return "User Unauthorized" without a browser-solved session, but the SSR
  HTML itself already has everything needed).
- Detail: the full job (description, responsibilities, qualifications, exact
  locations, ISO posted date) is embedded as a JS string-literal argument to
  `window.__staticRouterHydrationData = JSON.parse("...")` — double-encoded
  (a JSON string containing escaped JSON), so it needs one extra json.loads
  after unescaping. See _parse_detail().

Apple jobs are tagged platform="apple".
"""
from __future__ import annotations
import html
import json
import re

from .common import text_get, parse_date, is_recent

SEARCH_URL = "https://jobs.apple.com/en-us/search"
BASE = "https://jobs.apple.com"
_UA = {"User-Agent": ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                      "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36")}

_CARD_RE = re.compile(
    r'job-title-link[^>]*><h3><a[^>]*href="([^"]+)"[^>]*>([^<]+)</a></h3>'
    r'.*?job-posted-date[^>]*>([^<]*)<'
    r'.*?job-title-location[^>]*>.*?<span[^>]*>Location</span><span[^>]*>([^<]*)<',
    re.DOTALL,
)
_HYDRATION_RE = re.compile(
    r'window\.__staticRouterHydrationData = JSON\.parse\((".*?")\);', re.DOTALL
)
_US_COUNTRIES = {"united states", "united states of america", "usa", "us"}

_PAGE_SIZE = 20
_MAX_PAGES_PER_QUERY = 15   # ~300 listings/query enumerated
_MAX_DETAIL_PER_CYCLE = 100


def _parse_search_page(doc: str) -> list[tuple[str, str, str, str]]:
    """Returns list of (href, title, posted_date_text, location_text)."""
    return _CARD_RE.findall(doc)


async def _search(query: str) -> list[tuple[str, str, str, str]]:
    cards: list[tuple[str, str, str, str]] = []
    for pg in range(1, _MAX_PAGES_PER_QUERY + 1):
        doc = await text_get(SEARCH_URL, headers=_UA, params={
            "search": query, "sort": "newest",
            "location": "united-states-USA", "page": pg,
        })
        if not doc:
            break
        page_cards = _parse_search_page(doc)
        if not page_cards:
            break
        cards.extend(page_cards)
    return cards


def _parse_detail(doc: str) -> dict | None:
    m = _HYDRATION_RE.search(doc)
    if not m:
        return None
    try:
        inner = json.loads(m.group(1))
        data = json.loads(inner)
        jd = data["loaderData"]["jobDetails"]["jobsData"]
    except (json.JSONDecodeError, KeyError, TypeError):
        return None

    parts = [jd.get("jobSummary", ""), jd.get("description", ""),
             jd.get("responsibilities", ""), jd.get("minimumQualifications", ""),
             jd.get("preferredQualifications", "")]
    desc = " ".join(re.sub(r"<[^>]+>", " ", p or "") for p in parts)
    desc = html.unescape(re.sub(r"\s+", " ", desc)).strip()

    locs = jd.get("locations") or []
    countries = {(l.get("countryName") or "").strip().lower() for l in locs}
    location = ", ".join(
        ", ".join(x for x in (l.get("city"), l.get("stateProvince")) if x) or l.get("countryName", "")
        for l in locs
    ) if locs else ""

    return {
        "title": jd.get("postingTitle", ""),
        "description": desc,
        "location": location,
        "posted_date": parse_date(jd.get("postDateInGMT", "")),
        "countries": countries,
    }


async def scrape_apple(roles: list[str] | None = None) -> list[dict]:
    from job_scanner.store import existing_urls
    known = existing_urls()
    queries = roles or ["Software Engineer"]

    seen_hrefs: set[str] = set()
    candidates: list[str] = []
    for q in queries:
        for href, title, posted_text, _loc in await _search(q):
            if href in seen_hrefs:
                continue
            seen_hrefs.add(href)
            url = BASE + href
            if url in known:
                continue
            candidates.append(url)
    candidates = candidates[:_MAX_DETAIL_PER_CYCLE]
    if not candidates:
        return []

    import asyncio
    sem = asyncio.Semaphore(8)

    async def _fetch(url: str) -> dict | None:
        async with sem:
            doc = await text_get(url, headers=_UA)
        if not doc:
            return None
        parsed = _parse_detail(doc)
        if not parsed or not parsed["description"]:
            return None
        job = {
            "title": parsed["title"], "company": "Apple", "url": url,
            "platform": "apple", "description": parsed["description"][:100000],
            "location": parsed["location"] or "United States",
            "posted_date": parsed["posted_date"],
        }
        if parsed["countries"] and not (parsed["countries"] & _US_COUNTRIES):
            job["screen_skip_reason"] = f"non-US ({', '.join(parsed['countries'])})"
        elif not is_recent(parsed["posted_date"]):
            return None
        return job

    results = await asyncio.gather(*[_fetch(u) for u in candidates], return_exceptions=True)
    jobs = [r for r in results if isinstance(r, dict)]
    jobs.sort(key=lambda j: j.get("posted_date", ""), reverse=True)
    return jobs

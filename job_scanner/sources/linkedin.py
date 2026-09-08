"""
LinkedIn — "Software Engineer" postings, filtered to the last hour, resolved
to their real external ATS destination (Greenhouse/Workday/Ashby/etc.).

Two-phase design, matching what was validated by hand before building this:

  1. DISCOVERY (anonymous, no login, cheap): LinkedIn's public "guest" search
     endpoint returns title/company/link for a keyword+location+time-window
     query with no auth needed. Filtered here to postings from the last hour
     via f_TPR=r3600.

  2. RESOLUTION (authenticated, expensive/rate-limited, capped): logged-out
     job pages don't expose the real "Apply" destination — LinkedIn only
     renders it (as an <a href="…/safety/go/?url=...">) once we hold a valid
     session. So a SPARE LinkedIn account's saved session
     (data/linkedin_auth/state.json) drives a headless Playwright page per
     candidate to (a) skip Easy Apply jobs entirely and (b) decode the real
     destination URL from LinkedIn's own outbound-link wrapper for everything
     else. That destination URL — not the LinkedIn URL — is what gets fed
     into the normal scan/screen pipeline, tagged platform="linkedin".

Every LinkedIn job ID we inspect (any outcome) is recorded in
job_scanner.linkedin_store so a reposted/bumped listing is never re-opened
with the authenticated session on a later cycle — see that module for why.

Because LinkedIn's own listing date is only day-granular and unreliable for
freshness (bumped old postings show today's date too), the posted_date we
save is simply "now" — we already know the job matched the past-1-hour
filter at discovery time, so this is accurate enough without needing a
per-ATS date scraper.
"""
from __future__ import annotations
import asyncio
import re
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path

from .common import text_get

STATE_PATH = Path(__file__).parent.parent.parent / "data" / "linkedin_auth" / "state.json"
GUEST_SEARCH_URL = "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"

KEYWORDS = "Software Engineer"
LOCATION = "United States"

_UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36")
_HEADERS = {"User-Agent": _UA}

_TITLE_RE = re.compile(r'base-search-card__title">\s*([^<]+?)\s*</h3>')
_COMPANY_RE = re.compile(r'base-search-card__subtitle">\s*<a[^>]*>\s*([^<]+?)\s*</a>')
_HREF_RE = re.compile(r'href="(https://www\.linkedin\.com/jobs/view/[^"?]+)')
_ID_RE = re.compile(r"-(\d+)$")

_PAGE_SIZE = 25
_MAX_LIST_PAGES = 10          # anonymous discovery: up to 250 listings scanned, cheap
_MAX_RESOLVE_PER_CYCLE = 25   # authenticated resolutions per cycle — the expensive part
_NAV_TIMEOUT_MS = 30000
_BETWEEN_NAV_DELAY = 4        # seconds — politeness on the authenticated session


def _parse_cards(doc: str) -> list[tuple[str, str, str, str]]:
    """Returns list of (job_id, title, company, linkedin_url)."""
    titles = _TITLE_RE.findall(doc)
    companies = _COMPANY_RE.findall(doc)
    hrefs = _HREF_RE.findall(doc)
    out = []
    for i, href in enumerate(hrefs):
        m = _ID_RE.search(href)
        if not m:
            continue
        job_id = m.group(1)
        title = titles[i] if i < len(titles) else ""
        company = companies[i] if i < len(companies) else ""
        out.append((job_id, title.strip(), company.strip(), href))
    return out


async def _discover() -> list[tuple[str, str, str, str]]:
    """Anonymous guest-endpoint search: 'Software Engineer', US, past 1 hour."""
    seen_ids: set[str] = set()
    cards: list[tuple[str, str, str, str]] = []
    for page in range(_MAX_LIST_PAGES):
        doc = await text_get(GUEST_SEARCH_URL, headers=_HEADERS, params={
            "keywords": KEYWORDS,
            "location": LOCATION,
            "f_TPR": "r3600",
            "sortBy": "DD",
            "start": page * _PAGE_SIZE,
        })
        if not doc:
            break
        page_cards = _parse_cards(doc)
        if not page_cards:
            break
        new_this_page = 0
        for c in page_cards:
            if c[0] not in seen_ids:
                seen_ids.add(c[0])
                cards.append(c)
                new_this_page += 1
        if new_this_page == 0:
            break
        await asyncio.sleep(0.3)  # polite between anonymous pages too
    return cards


async def _resolve_candidates(candidates: list[tuple[str, str, str, str]],
                              known_urls: set[str]) -> list[dict]:
    """Authenticated resolution: skip Easy Apply, decode the real destination URL
    for everything else. Sequential + delayed on purpose — authenticated LinkedIn
    traffic is rate-limited far more aggressively than anonymous requests."""
    from playwright.async_api import async_playwright
    from job_scanner.linkedin_store import mark_seen

    jobs: list[dict] = []
    now_iso = datetime.now(tz=timezone.utc).isoformat()

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        ctx = await browser.new_context(
            storage_state=str(STATE_PATH),
            user_agent=_UA,
            viewport={"width": 1280, "height": 900},
        )
        page = await ctx.new_page()

        for job_id, title, company, linkedin_url in candidates:
            try:
                await page.goto(linkedin_url, wait_until="domcontentloaded", timeout=_NAV_TIMEOUT_MS)
                await page.wait_for_timeout(1200)

                if await page.locator('button:has-text("Easy Apply")').count() > 0:
                    mark_seen(job_id, "easy_apply")
                    await page.wait_for_timeout(_BETWEEN_NAV_DELAY * 1000)
                    continue

                dest_url = None
                for a in await page.locator('a[href*="safety/go"]').all():
                    href = await a.get_attribute("href")
                    if not href:
                        continue
                    q = urllib.parse.parse_qs(urllib.parse.urlparse(href).query)
                    if q.get("url"):
                        dest_url = urllib.parse.unquote(q["url"][0])
                        break

                if not dest_url:
                    mark_seen(job_id, "no_redirect_found")
                    await page.wait_for_timeout(_BETWEEN_NAV_DELAY * 1000)
                    continue

                if dest_url in known_urls:
                    mark_seen(job_id, "duplicate_destination")
                    await page.wait_for_timeout(_BETWEEN_NAV_DELAY * 1000)
                    continue

                body = await page.inner_text("body")
                desc = re.sub(r"\s+\n", "\n", body)
                m = re.search(re.escape(title), desc) if title else None
                if m:
                    desc = desc[m.start():]

                jobs.append({
                    "title": title,
                    "company": company,
                    "url": dest_url,
                    "platform": "linkedin",
                    "description": desc[:100000],
                    "location": "United States",
                    "posted_date": now_iso,
                })
                mark_seen(job_id, "saved")
            except Exception:
                mark_seen(job_id, "error")
            await page.wait_for_timeout(_BETWEEN_NAV_DELAY * 1000)

        await browser.close()
    return jobs


async def scrape_linkedin() -> list[dict]:
    if not STATE_PATH.exists():
        return []

    from job_scanner.store import existing_urls
    from job_scanner.linkedin_store import existing_linkedin_ids

    known_urls = existing_urls()
    already_checked = existing_linkedin_ids()

    cards = await _discover()
    unresolved = [c for c in cards if c[0] not in already_checked][:_MAX_RESOLVE_PER_CYCLE]
    if not unresolved:
        return []

    return await _resolve_candidates(unresolved, known_urls)

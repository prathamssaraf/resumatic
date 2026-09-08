"""
Meta careers (metacareers.com) — browser-driven scraper.

Meta blocks plain HTTP (400) and requires JS-computed CSRF tokens, so — like the
maangcrawler project — we drive a real (headless) Chromium via Playwright, let
Meta's own JavaScript fetch the jobs, and intercept the GraphQL response. The
job list (job_search_with_featured_jobs_v2.all_jobs) has title/locations/teams
but no description, so we read each job's detail page for the JD text.

This needs a real (headless) browser, so it's heavier than the other sources,
but it's wired into the normal 20-min daemon loop like everything else — capped
per cycle (max_detail) and guarded with a timeout so a hang can't stall the
whole scan. Can still be run standalone via `uv run python main.py meta`.
"""
from __future__ import annotations
import asyncio
import json
import re
from datetime import date

SEARCH_URL = "https://www.metacareers.com/jobs?sort_by_new=true&roles[0]=Full%20time%20employment"
_UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36")

_US_STATES = {
    "AL","AK","AZ","AR","CA","CO","CT","DE","FL","GA","HI","ID","IL","IN","IA","KS",
    "KY","LA","ME","MD","MA","MI","MN","MS","MO","MT","NE","NV","NH","NJ","NM","NY",
    "NC","ND","OH","OK","OR","PA","RI","SC","SD","TN","TX","UT","VT","VA","WA","WV","WI","WY","DC",
}
# only bother fetching detail pages for plausibly-technical roles (bounds browsing)
_TECH_TITLE = re.compile(
    r"engineer|software|developer|machine learning|\bml\b|\bai\b|data scien|data engineer|"
    r"research scien|research engineer|infrastructure|security|systems|backend|front[- ]?end|"
    r"full[- ]?stack|technical program|solutions engineer|network engineer|hardware|silicon|"
    r"scientist|analyst|quantitative|production engineer", re.I)


def _is_us(locations: list[str]) -> bool:
    for loc in locations or []:
        l = loc.strip()
        if re.search(r",\s*(US|USA|United States)\b", l, re.I):
            return True
        m = re.search(r",\s*([A-Z]{2})\b", l)
        if m and m.group(1) in _US_STATES:
            return True
        if l.lower() in ("remote, us", "remote"):
            return True
    return False


async def scrape_meta(max_detail: int = 150, headless: bool = True) -> list[dict]:
    from playwright.async_api import async_playwright
    from job_scanner.store import existing_urls

    known = existing_urls()
    all_jobs_body: list[str] = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=headless)
        ctx = await browser.new_context(user_agent=_UA, viewport={"width": 1440, "height": 900},
                                        locale="en-US")
        page = await ctx.new_page()

        async def _grab(resp):
            if "graphql" in resp.url:
                try:
                    b = await resp.text()
                    if "all_jobs" in b and len(b) > 50000:
                        all_jobs_body.append(b)
                except Exception:
                    pass
        page.on("response", _grab)

        # networkidle never fires on Meta (persistent long-poll connections), so
        # load, then poll for the intercepted jobs response instead of waiting.
        try:
            await page.goto(SEARCH_URL, wait_until="domcontentloaded", timeout=45000)
        except Exception:
            pass
        for _ in range(30):
            if all_jobs_body:
                break
            await page.wait_for_timeout(1000)

        listing = []
        if all_jobs_body:
            d = json.loads(all_jobs_body[-1])
            listing = d["data"]["job_search_with_featured_jobs_v2"]["all_jobs"]

        # filter: US + technical title + not already stored, then cap
        cands = []
        for j in listing:
            title = j.get("title", "")
            url = f"https://www.metacareers.com/jobs/{j.get('id')}/"
            if url in known:
                continue
            if not _is_us(j.get("locations", [])):
                continue
            if not _TECH_TITLE.search(title):
                continue
            cands.append({"id": j.get("id"), "title": title,
                          "location": ", ".join(j.get("locations", [])[:2]), "url": url})
        cands = cands[:max_detail]

        # fetch each detail page's rendered text for the description
        out = []
        today = date.today().isoformat()
        for c in cands:
            try:
                await page.goto(c["url"], wait_until="domcontentloaded", timeout=45000)
                await page.wait_for_timeout(700)
                txt = await page.inner_text("body")
            except Exception:
                continue
            desc = re.sub(r"\s+\n", "\n", txt)
            # trim the top nav ("Skip to main content … Blog Podcasts …")
            m = re.search(re.escape(c["title"]), desc)
            if m:
                desc = desc[m.start():]
            out.append({
                "title": c["title"],
                "company": "Meta",
                "url": c["url"],
                "platform": "meta",
                "description": desc[:100000],
                "location": c["location"],
                "posted_date": today,
            })
        await browser.close()
    return out

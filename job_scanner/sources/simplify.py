"""
SimplifyJobs New-Grad-Positions feed.
- First run: last 7 days only
- Subsequent runs: only jobs newer than last scan
- Fetches full description from the job URL (ATS-aware)
"""
from __future__ import annotations
import re
import time
from pathlib import Path
from .common import json_get, parse_date, strip_html
import httpx

LISTINGS_URL = (
    "https://raw.githubusercontent.com/SimplifyJobs/New-Grad-Positions"
    "/dev/.github/scripts/listings.json"
)

_STATE_FILE = Path(__file__).parent.parent.parent / "data" / "simplify_last_scan.txt"

_GOOD_CATEGORIES = {
    "Software", "Software Engineering", "AI/ML/Data",
    "Data Science, AI & Machine Learning",
}

_NO_SPONSORSHIP = {
    "Does Not Offer Sponsorship",
    "U.S. Citizenship is Required",
}


def _last_scan_ts() -> int:
    """Unix timestamp of last simplify scan. Default: 7 days ago."""
    if _STATE_FILE.exists():
        try:
            return int(_STATE_FILE.read_text().strip())
        except ValueError:
            pass
    return int(time.time()) - 7 * 86400


def _save_scan_ts() -> None:
    _STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    _STATE_FILE.write_text(str(int(time.time())))


def _detect_ats(url: str) -> str | None:
    if "greenhouse.io" in url or "boards-api.greenhouse.io" in url:
        return "greenhouse"
    if "lever.co" in url:
        return "lever"
    if "ashbyhq.com" in url:
        return "ashby"
    return None


def _greenhouse_job_id(url: str) -> str | None:
    # https://job-boards.greenhouse.io/{slug}/jobs/{id}
    m = re.search(r"greenhouse\.io/[^/]+/jobs/(\d+)", url)
    return m.group(1) if m else None


async def _fetch_description(url: str) -> str:
    """Fetch full job description from the apply URL."""
    ats = _detect_ats(url)

    try:
        if ats == "greenhouse":
            job_id = _greenhouse_job_id(url)
            if job_id:
                data = await json_get(
                    f"https://boards-api.greenhouse.io/v1/boards/jobs/{job_id}"
                )
                if isinstance(data, dict) and data.get("content"):
                    return strip_html(data["content"])[:100000]

        if ats == "lever":
            # https://jobs.lever.co/{slug}/{id}
            m = re.search(r"lever\.co/([^/]+)/([a-f0-9-]+)", url)
            if m:
                slug, job_id = m.group(1), m.group(2)
                data = await json_get(
                    f"https://api.lever.co/v0/postings/{slug}/{job_id}"
                )
                if isinstance(data, dict):
                    return (
                        (data.get("descriptionPlain") or "") + "\n" +
                        (data.get("additionalPlain") or "")
                    ).strip()[:100000]

        if ats == "ashby":
            # https://jobs.ashbyhq.com/{slug}/{id}
            m = re.search(r"ashbyhq\.com/([^/]+)/([a-f0-9-]+)", url)
            if m:
                job_id = m.group(2)
                data = await json_get(
                    f"https://api.ashbyhq.com/posting-api/job-posting/{job_id}"
                )
                if isinstance(data, dict):
                    return strip_html(
                        data.get("descriptionHtml") or
                        data.get("descriptionPlain") or ""
                    )[:100000]

        # Fallback: plain HTTP fetch
        async with httpx.AsyncClient(timeout=15, follow_redirects=True, verify=False) as c:
            r = await c.get(url, headers={"User-Agent": "Mozilla/5.0"})
            if r.status_code == 200:
                text = strip_html(r.text)
                # Strip obvious nav/footer noise — keep middle chunk
                return text[500:3500] if len(text) > 500 else text

    except Exception:
        pass

    return ""


async def scrape_simplify(roles: list[str]) -> list[dict]:
    data = await json_get(LISTINGS_URL)
    if not isinstance(data, list):
        return []

    cutoff = _last_scan_ts()
    candidates = []
    for j in data:
        if not j.get("active") or not j.get("is_visible"):
            continue
        if j.get("sponsorship") in _NO_SPONSORSHIP:
            continue
        if j.get("category") and j["category"] not in _GOOD_CATEGORIES:
            continue
        if (j.get("date_posted") or 0) < cutoff:
            continue
        candidates.append(j)

    import asyncio
    from rich.console import Console
    console = Console()
    console.print(f"  [dim]Simplify: {len(candidates)} new entries since last scan[/dim]")

    # Fetch descriptions concurrently (cap at 20 parallel to be polite)
    sem = asyncio.Semaphore(20)

    async def fetch_one(j: dict) -> dict:
        async with sem:
            locs = j.get("locations", [])
            loc = ", ".join(locs[:2]) if locs else ""
            desc = await _fetch_description(j.get("url", ""))
            if not desc:
                title = j.get("title", "")
                company = j.get("company_name", "")
                desc = f"{title} at {company}. Location: {loc}."
            return {
                "title": j.get("title", ""),
                "company": j.get("company_name", ""),
                "url": j.get("url", ""),
                "platform": "simplify",
                "description": desc,
                "location": loc,
                "salary": "",
                "posted_date": parse_date(j.get("date_posted")),
                "sponsorship": j.get("sponsorship", ""),
            }

    results = await asyncio.gather(*[fetch_one(j) for j in candidates], return_exceptions=True)
    _save_scan_ts()
    return [r for r in results if isinstance(r, dict)]

"""
vanshb03/New-Grad-2026 feed — same Pitt-CSC-style listings.json format as
SimplifyJobs, sourced by a different bot ("cvrve-bot"), so it catches postings
Simplify's own bot misses. No 'category' field on any entry (unlike Simplify),
so no category pre-filter here — role-type screening is left entirely to the
normal LLM criteria (role_type, level, etc. in job_scanner/quality.py), same
as every other source with no structured category of its own.

- First run: last 7 days only
- Subsequent runs: only jobs newer than last scan
- Fetches full description from the job URL (ATS-aware)
"""
from __future__ import annotations
import time
from pathlib import Path
from .common import json_get, parse_date, fetch_ats_description

LISTINGS_URL = (
    "https://raw.githubusercontent.com/vanshb03/New-Grad-2026"
    "/dev/.github/scripts/listings.json"
)

_STATE_FILE = Path(__file__).parent.parent.parent / "data" / "vanshb03_last_scan.txt"

_NO_SPONSORSHIP = {
    "Does Not Offer Sponsorship",
    "U.S. Citizenship is Required",
}


def _last_scan_ts() -> int:
    if _STATE_FILE.exists():
        try:
            return int(_STATE_FILE.read_text().strip())
        except ValueError:
            pass
    return int(time.time()) - 7 * 86400


def _save_scan_ts() -> None:
    _STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    _STATE_FILE.write_text(str(int(time.time())))


async def scrape_vanshb03(roles: list[str]) -> list[dict]:
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
        if (j.get("date_posted") or 0) < cutoff:
            continue
        candidates.append(j)

    import asyncio
    from rich.console import Console
    console = Console()
    console.print(f"  [dim]vanshb03: {len(candidates)} new entries since last scan[/dim]")

    sem = asyncio.Semaphore(20)

    async def fetch_one(j: dict) -> dict:
        async with sem:
            locs = j.get("locations", [])
            loc = ", ".join(locs[:2]) if locs else ""
            desc = await fetch_ats_description(j.get("url", ""))
            if not desc:
                title = j.get("title", "")
                company = j.get("company_name", "")
                desc = f"{title} at {company}. Location: {loc}."
            return {
                "title": j.get("title", ""),
                "company": j.get("company_name", ""),
                "url": j.get("url", ""),
                "platform": "vanshb03",
                "description": desc,
                "location": loc,
                "salary": "",
                "posted_date": parse_date(j.get("date_posted")),
                "sponsorship": j.get("sponsorship", ""),
            }

    results = await asyncio.gather(*[fetch_one(j) for j in candidates], return_exceptions=True)
    _save_scan_ts()
    return [r for r in results if isinstance(r, dict)]

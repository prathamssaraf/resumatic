"""
Workday (myworkdayjobs.com) CXS API scraper for major employers.

Workday exposes a per-tenant JSON API:
  POST https://{host}/wday/cxs/{tenant}/{site}/jobs   -> paged posting list
  GET  https://{host}/wday/cxs/{tenant}/{site}{path}  -> full posting (desc, country, date)

The list gives title + postedOn (relative) + externalPath; the detail gives the
description, country (for US filter) and startDate (for recency). Each company is
huge, so we: cap pages, pre-filter stale by postedOn, fetch a detail page only for
a recent URL not already stored, and tag non-US ones with screen_skip_reason so
they're saved once as 'skip' and never re-fetched (same approach as Citi).

Workday jobs are tagged platform="workday" and screened with the global criteria.
"""
from __future__ import annotations
import asyncio
import html
import json
import re
from datetime import datetime, timezone

import httpx

from .common import is_recent, parse_date

# (company, host, tenant, site) — all live-verified.
WORKDAY_SITES: list[tuple[str, str, str, str]] = [
    ("NVIDIA",      "nvidia.wd5.myworkdayjobs.com",     "nvidia",      "NVIDIAExternalCareerSite"),
    ("Salesforce",  "salesforce.wd12.myworkdayjobs.com", "salesforce",  "External_Career_Site"),
    ("Mastercard",  "mastercard.wd1.myworkdayjobs.com",  "mastercard",  "CorporateCareers"),
    ("Wells Fargo", "wf.wd1.myworkdayjobs.com",          "wf",          "WellsFargoJobs"),
    ("PayPal",      "paypal.wd1.myworkdayjobs.com",      "paypal",      "jobs"),
    ("CrowdStrike", "crowdstrike.wd5.myworkdayjobs.com", "crowdstrike", "crowdstrikecareers"),
    ("Autodesk",    "autodesk.wd1.myworkdayjobs.com",    "autodesk",    "Ext"),
    ("Workday",     "workday.wd5.myworkdayjobs.com",     "workday",     "Workday"),
    # Batch 2 — verified major employers
    ("CVS Health",     "cvshealth.wd1.myworkdayjobs.com",       "cvshealth",      "CVS_Health_Careers"),
    ("Micron",         "micron.wd1.myworkdayjobs.com",          "micron",         "External"),
    ("Target",         "target.wd5.myworkdayjobs.com",          "target",         "TargetCareers"),
    ("PNC",            "pnc.wd5.myworkdayjobs.com",             "pnc",            "External"),
    ("T-Mobile",       "tmobile.wd1.myworkdayjobs.com",         "tmobile",        "External"),
    ("Truist",         "truist.wd1.myworkdayjobs.com",          "truist",         "Careers"),
    ("Comcast",        "comcast.wd5.myworkdayjobs.com",         "comcast",        "Comcast_Careers"),
    ("General Motors", "generalmotors.wd5.myworkdayjobs.com",   "generalmotors",  "Careers_GM"),
    ("HP",             "hp.wd5.myworkdayjobs.com",              "hp",             "ExternalCareerSite"),
    ("Intel",          "intel.wd1.myworkdayjobs.com",           "intel",          "External"),
    ("AIG",            "aig.wd1.myworkdayjobs.com",             "aig",            "AIG"),
    ("BlackRock",      "blackrock.wd1.myworkdayjobs.com",       "blackrock",      "BlackRock_Professional"),
    ("Zillow",         "zillow.wd5.myworkdayjobs.com",          "zillow",         "Zillow_Group_External"),
    ("Swift",          "swift.wd3.myworkdayjobs.com",           "swift",          "Join-Swift"),
]

_UA = {"User-Agent": ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                      "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"),
       "Accept": "application/json"}
_US_COUNTRIES = {"united states", "united states of america", "usa", "us"}
_PAGE = 20                    # Workday's page size
_MAX_PAGES_PER_CO = 20        # cap list pages per company per cycle (~400 postings)
_MAX_DETAIL_PER_CO = 25       # cap detail fetches per company per cycle
_RECENT_DAYS = 7


def _posted_days(s: str) -> int:
    """Parse Workday's relative 'postedOn' to a day count. -1 = unknown (keep)."""
    s = (s or "").lower()
    if "today" in s or "just posted" in s:
        return 0
    if "yesterday" in s:
        return 1
    m = re.search(r"(\d+)\+?\s*day", s)
    if m:
        return int(m.group(1))
    m = re.search(r"(\d+)\+?\s*month", s)
    if m:
        return int(m.group(1)) * 30
    return -1


async def _list_page(client: httpx.AsyncClient, host, tenant, site, offset) -> list[dict]:
    url = f"https://{host}/wday/cxs/{tenant}/{site}/jobs"
    body = {"appliedFacets": {}, "limit": _PAGE, "offset": offset, "searchText": ""}
    try:
        r = await client.post(url, json=body, headers=_UA)
        r.raise_for_status()
        return r.json().get("jobPostings", []) or []
    except Exception:
        return []


async def _detail(client: httpx.AsyncClient, host, tenant, site, path) -> dict | None:
    url = f"https://{host}/wday/cxs/{tenant}/{site}{path}"
    try:
        r = await client.get(url, headers=_UA)
        r.raise_for_status()
        return r.json().get("jobPostingInfo", {}) or None
    except Exception:
        return None


async def _scrape_company(client, company, host, tenant, site, known: set[str]) -> list[dict]:
    # 1. Enumerate list pages; stop early once a whole page is stale (list is
    #    roughly newest-first). Collect recent, unseen postings.
    site_url = f"https://{host}/{site}"
    candidates: list[dict] = []
    for pg in range(_MAX_PAGES_PER_CO):
        postings = await _list_page(client, host, tenant, site, pg * _PAGE)
        if not postings:
            break
        page_fresh = 0
        for p in postings:
            path = p.get("externalPath", "")
            if not path:
                continue
            days = _posted_days(p.get("postedOn", ""))
            if days == -1 or days <= _RECENT_DAYS:
                page_fresh += 1
                url = site_url + path
                if url not in known:
                    candidates.append({"path": path, "url": url})
        if page_fresh == 0:            # whole page stale -> assume the rest is too
            break
        if len(candidates) >= _MAX_DETAIL_PER_CO:
            break
    candidates = candidates[:_MAX_DETAIL_PER_CO]

    # 2. Fetch detail for each candidate (US + recency + description).
    out: list[dict] = []
    for c in candidates:
        info = await _detail(client, host, tenant, site, c["path"])
        if not info:
            continue
        country = ""
        cc = info.get("country")
        if isinstance(cc, dict):
            country = str(cc.get("descriptor", "")).strip().lower()
        location = info.get("location", "") or ""
        posted = parse_date(info.get("startDate", ""))
        desc = re.sub(r"<[^>]+>", " ", info.get("jobDescription", "") or "")
        desc = html.unescape(re.sub(r"\s+", " ", desc)).strip()
        job = {
            "title": info.get("title", ""),
            "company": company,
            "url": c["url"],
            "platform": "workday",
            "description": desc[:100000],
            "location": location or country or "United States",
            "posted_date": posted,
        }
        if country and country not in _US_COUNTRIES:
            job["screen_skip_reason"] = f"non-US ({country})"
        elif not is_recent(posted):
            continue  # US but stale — drop (postedOn pre-filter usually catches it)
        out.append(job)
    return out


async def scrape_workday(roles: list[str] | None = None) -> list[dict]:
    from job_scanner.store import existing_urls
    known = existing_urls()
    async with httpx.AsyncClient(timeout=30, follow_redirects=True, verify=False) as client:
        results = await asyncio.gather(
            *[_scrape_company(client, *site, known) for site in WORKDAY_SITES],
            return_exceptions=True,
        )
    jobs: list[dict] = []
    for r in results:
        if isinstance(r, list):
            jobs.extend(r)
    jobs.sort(key=lambda j: j.get("posted_date", ""), reverse=True)
    return jobs

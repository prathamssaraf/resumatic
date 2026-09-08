"""
Free job aggregator APIs: RemoteOK, Remotive, Jobicy.
"""
from __future__ import annotations
from .common import json_get, parse_date, strip_html, is_recent

REMOTEOK_URL = "https://remoteok.com/api"
REMOTIVE_URL = "https://remotive.com/api/remote-jobs"
JOBICY_URL = "https://jobicy.com/api/v2/remote-jobs"
THEMUSE_URL = "https://www.themuse.com/api/public/jobs"
HIMALAYAS_URL = "https://himalayas.app/jobs/api"


def _matches(text: str, roles: list[str]) -> bool:
    t = text.lower()
    return not roles or any(r.lower() in t for r in roles)


async def scrape_remoteok(roles: list[str]) -> list[dict]:
    data = await json_get(REMOTEOK_URL, headers={"User-Agent": "jobs-auto-scanner/1.0"})
    if not isinstance(data, list):
        return []
    results = []
    for j in data:
        if not isinstance(j, dict) or not j.get("position"):
            continue
        title = j.get("position", "")
        tags = " ".join(j.get("tags", []))
        if not _matches(f"{title} {tags}", roles):
            continue
        posted = parse_date(j.get("epoch"))
        if not is_recent(posted):
            continue
        sal = ""
        if j.get("salary_min"):
            sal = f"${j['salary_min']:,}–${j.get('salary_max', j['salary_min']):,}/yr"
        results.append({
            "title": title,
            "company": j.get("company", ""),
            "url": j.get("url", f"https://remoteok.com/l/{j.get('id', '')}"),
            "platform": "remoteok",
            "description": strip_html(j.get("description", ""))[:100000],
            "location": j.get("location", "Remote"),
            "salary": sal,
            "posted_date": posted,
        })
    return results


async def scrape_remotive(roles: list[str]) -> list[dict]:
    data = await json_get(REMOTIVE_URL, params={"limit": 100})
    jobs = data.get("jobs", []) if isinstance(data, dict) else []
    results = []
    for j in jobs:
        title = j.get("title", "")
        if not _matches(f"{title} {j.get('category', '')}", roles):
            continue
        posted = parse_date(j.get("publication_date", ""))
        if not is_recent(posted):
            continue
        results.append({
            "title": title,
            "company": j.get("company_name", ""),
            "url": j.get("url", ""),
            "platform": "remotive",
            "description": strip_html(j.get("description", ""))[:100000],
            "location": j.get("candidate_required_location", "Remote"),
            "salary": j.get("salary", ""),
            "posted_date": posted,
        })
    return results


async def scrape_jobicy(roles: list[str]) -> list[dict]:
    data = await json_get(JOBICY_URL, params={"count": 50})
    jobs = data.get("jobs", []) if isinstance(data, dict) else []
    results = []
    for j in jobs:
        title = j.get("jobTitle", "")
        if not _matches(title, roles):
            continue
        posted = parse_date(j.get("pubDate", ""))
        if not is_recent(posted):
            continue
        sal_min = j.get("annualSalaryMin")
        sal_max = j.get("annualSalaryMax")
        curr = j.get("salaryCurrency", "USD")
        sal = f"{curr} {sal_min:,}–{sal_max:,}/yr" if sal_min else ""
        results.append({
            "title": title,
            "company": j.get("companyName", ""),
            "url": j.get("url", ""),
            "platform": "jobicy",
            "description": strip_html(j.get("jobDescription", ""))[:100000],
            "location": j.get("jobGeo", "Remote"),
            "salary": sal,
            "posted_date": posted,
        })
    return results


# The Muse — large board with category + level filters. We pull early-career
# engineering roles directly so the candidate set arrives pre-scoped.
_MUSE_CATEGORIES = ["Software Engineering", "Computer and IT", "Data Science", "Data and Analytics"]
_MUSE_LEVELS = ["Entry Level", "Mid Level"]


async def scrape_themuse(roles: list[str], pages: int = 3) -> list[dict]:
    results = []
    for page in range(pages):
        data = await json_get(THEMUSE_URL, params={
            "category": _MUSE_CATEGORIES,
            "level": _MUSE_LEVELS,
            "page": page,
        })
        items = data.get("results", []) if isinstance(data, dict) else []
        if not items:
            break
        for j in items:
            title = j.get("name", "")
            posted = parse_date(j.get("publication_date", ""))
            if not is_recent(posted):
                continue
            loc = ", ".join(l.get("name", "") for l in j.get("locations", []) if l.get("name")) or "Flexible / Remote"
            results.append({
                "title": title,
                "company": (j.get("company") or {}).get("name", ""),
                "url": (j.get("refs") or {}).get("landing_page", ""),
                "platform": "themuse",
                "description": strip_html(j.get("contents", "") or "")[:100000],
                "location": loc,
                "posted_date": posted,
            })
    return results


# Himalayas — large remote-job board. Noisier (lots of non-eng / global roles),
# so we keep the role keyword filter to bound the candidate set.
async def scrape_himalayas(roles: list[str], limit: int = 200) -> list[dict]:
    data = await json_get(HIMALAYAS_URL, params={"limit": limit})
    jobs = data.get("jobs", []) if isinstance(data, dict) else []
    results = []
    for j in jobs:
        title = j.get("title", "")
        cats = " ".join(j.get("categories", []) or []) if isinstance(j.get("categories"), list) else ""
        if not _matches(f"{title} {cats}", roles):
            continue
        posted = parse_date(j.get("pubDate"))
        if not is_recent(posted):
            continue
        locs = j.get("locationRestrictions")
        loc = ", ".join(locs) if isinstance(locs, list) and locs else "Remote"
        results.append({
            "title": title,
            "company": j.get("companyName", ""),
            "url": j.get("applicationLink") or j.get("guid", ""),
            "platform": "himalayas",
            "description": strip_html(j.get("description", "") or "")[:100000],
            "location": loc,
            "posted_date": posted,
        })
    return results

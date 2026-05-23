"""
ATS board scrapers: Greenhouse, Lever, Ashby, Workable.
All are free public APIs — no auth required.
"""
from __future__ import annotations
from .common import json_get, parse_date, strip_html


async def scrape_greenhouse(slug: str) -> list[dict]:
    data = await json_get(
        f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs",
        params={"content": "true"},
    )
    jobs = data.get("jobs", []) if isinstance(data, dict) else []
    results = []
    for j in jobs:
        loc = ""
        if j.get("offices"):
            loc = j["offices"][0].get("name", "")
        elif j.get("location"):
            loc = j["location"].get("name", "")
        desc = strip_html(j.get("content", ""))
        results.append({
            "title": j.get("title", ""),
            "company": slug.replace("-", " ").title(),
            "url": j.get("absolute_url", ""),
            "platform": "greenhouse",
            "description": desc[:3000],
            "location": loc,
            "posted_date": parse_date(j.get("updated_at", "")),
        })
    return results


async def scrape_lever(slug: str) -> list[dict]:
    data = await json_get(f"https://api.lever.co/v0/postings/{slug}?mode=json")
    jobs = data if isinstance(data, list) else []
    results = []
    for j in jobs:
        cats = j.get("categories", {})
        loc = cats.get("location", cats.get("allLocations", [""])[0] if cats.get("allLocations") else "")
        desc = j.get("descriptionPlain", "") + "\n" + j.get("additionalPlain", "")
        results.append({
            "title": j.get("text", ""),
            "company": slug.replace("-", " ").title(),
            "url": j.get("hostedUrl", ""),
            "platform": "lever",
            "description": desc.strip()[:3000],
            "location": loc,
            "posted_date": parse_date(j.get("createdAt")),
        })
    return results


async def scrape_ashby(slug: str) -> list[dict]:
    data = await json_get(f"https://api.ashbyhq.com/posting-api/job-board/{slug}")
    jobs = data.get("jobs", []) if isinstance(data, dict) else []
    results = []
    for j in jobs:
        desc = j.get("descriptionPlain") or strip_html(j.get("descriptionHtml", ""))
        results.append({
            "title": j.get("title", ""),
            "company": slug.replace("-", " ").title(),
            "url": j.get("jobUrl") or j.get("applyUrl", ""),
            "platform": "ashby",
            "description": desc[:3000],
            "location": j.get("locationName", ""),
            "posted_date": parse_date(j.get("publishedDate") or j.get("updatedAt", "")),
        })
    return results


async def scrape_workable(slug: str) -> list[dict]:
    data = await json_get(f"https://www.workable.com/api/accounts/{slug}?details=true")
    if not isinstance(data, dict) or not data.get("jobs"):
        data = await json_get(f"https://apply.workable.com/api/v1/widget/accounts/{slug}")
    jobs = data.get("jobs", []) if isinstance(data, dict) else []
    results = []
    for j in jobs:
        loc = j.get("location", {})
        if isinstance(loc, dict):
            loc = loc.get("city") or loc.get("country") or ""
        desc = strip_html(j.get("description", "") + "\n" + j.get("requirements", ""))
        shortcode = j.get("shortcode", "")
        url = j.get("url") or j.get("application_url") or f"https://apply.workable.com/{slug}/j/{shortcode}/"
        results.append({
            "title": j.get("title") or j.get("full_title", ""),
            "company": slug.replace("-", " ").title(),
            "url": url,
            "platform": "workable",
            "description": desc.strip()[:3000],
            "location": str(loc),
            "posted_date": parse_date(j.get("published_on") or j.get("created_at", "")),
        })
    return results

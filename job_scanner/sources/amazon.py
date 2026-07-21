"""
Amazon careers (amazon.jobs) — public JSON search API, no browser needed.

https://www.amazon.jobs/en/search.json already returns the full description,
qualifications, country, and posted_date in the SAME response as the listing —
no per-job detail fetch required. Bounded to a handful of technical categories
to keep volume sane (Amazon's full catalog spans every job function globally).
"""
from __future__ import annotations
import re

from .common import json_get, parse_date, is_recent

BASE = "https://www.amazon.jobs/en/search.json"
_UA = {"User-Agent": ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                      "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36")}
_CATEGORIES = [
    "software-development", "machine-learning-science", "data-science", "solutions-architect",
]
_US_COUNTRIES = {"usa", "us", "united states", "united states of america"}
_PAGE = 100
_MAX_PAGES_PER_CATEGORY = 5   # ~500 postings/category/cycle cap


async def scrape_amazon(roles: list[str] | None = None) -> list[dict]:
    from job_scanner.store import existing_urls
    known = existing_urls()
    out: list[dict] = []
    seen_ids: set[str] = set()

    for cat in _CATEGORIES:
        for pg in range(_MAX_PAGES_PER_CATEGORY):
            data = await json_get(BASE, params={
                "offset": pg * _PAGE, "result_limit": _PAGE, "sort": "recent",
                "category[]": cat,
            }, headers=_UA)
            jobs = (data or {}).get("jobs", [])
            if not jobs:
                break
            for j in jobs:
                jid = j.get("id_icims") or j.get("id", "")
                path = j.get("job_path", "")
                url = f"https://www.amazon.jobs{path}" if path else ""
                if not url or jid in seen_ids or url in known:
                    continue
                seen_ids.add(jid)

                country = str(j.get("country_code", "")).strip().lower()
                posted = parse_date(j.get("posted_date", ""))
                desc = (j.get("description", "") or "") + "\n\n" + \
                       "Basic Qualifications:\n" + re.sub(r"<[^>]+>", " ", j.get("basic_qualifications", "") or "") + \
                       "\n\nPreferred Qualifications:\n" + re.sub(r"<[^>]+>", " ", j.get("preferred_qualifications", "") or "")
                desc = re.sub(r"<[^>]+>", " ", desc)
                desc = re.sub(r"\s+", " ", desc).strip()

                job = {
                    "title": j.get("title", ""),
                    "company": "Amazon",
                    "url": url,
                    "platform": "amazon",
                    "description": desc[:100000],
                    "location": j.get("normalized_location", "") or j.get("location", ""),
                    "posted_date": posted,
                }
                if country not in _US_COUNTRIES:
                    job["screen_skip_reason"] = f"non-US ({j.get('country_code', '?')})"
                elif not is_recent(posted):
                    continue  # US but stale — drop
                out.append(job)

            if len(jobs) < _PAGE:
                break  # last page for this category
    return out

"""
Hacker News "Who is Hiring?" thread scraper.
Uses Algolia API — no auth needed.
"""
from __future__ import annotations
import re
from .common import json_get, parse_date

HN_SEARCH = "https://hn.algolia.com/api/v1/search_by_date"
HN_ITEMS = "https://hn.algolia.com/api/v1/items/{}"


_SEEKING_WORK = re.compile(
    r"\b(seeking|looking for|available|open to|i am|i'm|my background|portfolio|"
    r"hire me|resume|cv\b|years of experience)\b", re.I
)
_JOB_OFFER = re.compile(
    r"\b(we are hiring|we're hiring|join us|we offer|apply|job opening|"
    r"full.time|part.time|contract|remote|onsite|salary|compensation|equity)\b", re.I
)


def _looks_like_job(text: str) -> bool:
    if not text or len(text) < 80:
        return False
    # Reject "seeking work" posts
    if _SEEKING_WORK.search(text[:200]):
        return False
    return _JOB_OFFER.search(text) is not None


def _extract_company(text: str, author: str) -> str:
    """Parse 'Company | Role | Location | ...' HN format."""
    first_line = text.split("\n")[0]
    parts = re.split(r"\s*[\|–—]\s*", first_line)
    if len(parts) >= 2:
        return parts[0].strip()
    return author or "Unknown"


def _matches(text: str, roles: list[str]) -> bool:
    t = text.lower()
    return not roles or any(r.lower() in t for r in roles)


async def scrape_hn_hiring(roles: list[str]) -> list[dict]:
    """Fetch latest 'Ask HN: Who is hiring?' thread and return matching job comments."""
    # Find the latest hiring thread
    search = await json_get(
        HN_SEARCH,
        params={
            "query": "Ask HN: Who is hiring?",
            "tags": "story",
            "hitsPerPage": 5,
        },
    )
    hits = search.get("hits", []) if isinstance(search, dict) else []
    story_id = None
    for hit in hits:
        title = hit.get("title", "")
        if "who is hiring" in title.lower() and "ask hn" in title.lower():
            story_id = hit.get("objectID")
            break

    if not story_id:
        return []

    thread = await json_get(HN_ITEMS.format(story_id))
    if not isinstance(thread, dict):
        return []

    results = []
    for comment in thread.get("children", []):
        if not isinstance(comment, dict):
            continue
        text = comment.get("text", "") or ""
        if not _looks_like_job(text) or not _matches(text, roles):
            continue
        author = comment.get("author", "")
        company = _extract_company(text, author)
        # Clean HTML from HN comments
        clean = re.sub(r"<[^>]+>", " ", text)
        clean = re.sub(r"&#x27;", "'", clean).strip()
        results.append({
            "title": f"Role at {company}",
            "company": company,
            "url": f"https://news.ycombinator.com/item?id={comment.get('id', '')}",
            "platform": "hn_hiring",
            "description": clean[:100000],
            "location": "",
            "salary": "",
            "posted_date": parse_date(comment.get("created_at", "")),
        })
    return results


async def scrape_hn_search(query: str) -> list[dict]:
    """Search HN 'Who is Hiring' story comments for a specific role query."""
    # Find the latest hiring thread first
    search = await json_get(
        HN_SEARCH,
        params={"query": "Ask HN: Who is hiring?", "tags": "story", "hitsPerPage": 3},
    )
    hits = search.get("hits", []) if isinstance(search, dict) else []
    story_ids = [h["objectID"] for h in hits
                 if "who is hiring" in h.get("title", "").lower()][:2]

    if not story_ids:
        return []

    from datetime import datetime, timezone, timedelta
    cutoff = int((datetime.now(tz=timezone.utc) - timedelta(days=35)).timestamp())
    data = await json_get(
        HN_SEARCH,
        params={
            "query": query,
            "tags": f"comment,story_{story_ids[0]}",
            "numericFilters": f"created_at_i>{cutoff}",
            "hitsPerPage": 25,
        },
    )
    hits = data.get("hits", []) if isinstance(data, dict) else []
    results = []
    for h in hits:
        text = h.get("comment_text", "") or ""
        if not _looks_like_job(text):
            continue
        author = h.get("author", "")
        company = _extract_company(text, author)
        if company == author:
            continue  # still just a username — skip
        results.append({
            "title": f"HN: {query}",
            "company": company,
            "url": f"https://news.ycombinator.com/item?id={h.get('objectID', '')}",
            "platform": "hn",
            "description": re.sub(r"<[^>]+>", " ", text).strip()[:100000],
            "location": "",
            "salary": "",
            "posted_date": parse_date(h.get("created_at", "")),
        })
    return results

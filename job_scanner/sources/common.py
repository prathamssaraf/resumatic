"""
Shared HTTP client and date utilities for all sources.
"""
from __future__ import annotations
import asyncio
import re
from datetime import datetime, timezone, timedelta
import httpx
import config

MAX_AGE_DAYS = config.MAX_JOB_AGE_DAYS
_HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; jobs-auto-scanner/1.0)",
    "Accept": "application/json",
}


async def json_get(url: str, params: dict | None = None, headers: dict | None = None) -> dict | list:
    h = {**_HEADERS, **(headers or {})}
    for attempt in range(4):
        try:
            async with httpx.AsyncClient(timeout=30, follow_redirects=True, verify=False) as c:
                resp = await c.get(url, params=params, headers=h)
                if resp.status_code == 429:
                    wait = int(resp.headers.get("Retry-After", 5 * (attempt + 1)))
                    await asyncio.sleep(wait)
                    continue
                resp.raise_for_status()
                return resp.json()
        except (httpx.TimeoutException, httpx.RemoteProtocolError, httpx.ConnectError):
            if attempt < 3:
                await asyncio.sleep(2 ** attempt)
    return {}


async def text_get(url: str, params: dict | None = None, headers: dict | None = None,
                   proxy: str | None = None) -> str:
    """Fetch a URL and return the raw response text (for HTML pages). '' on failure.
    Optional `proxy` (e.g. socks5://127.0.0.1:9050) routes this request only."""
    h = {**_HEADERS, "Accept": "text/html,application/xhtml+xml", **(headers or {})}
    timeout = 60 if proxy else 30  # proxied (Tor) requests are slower
    for attempt in range(4):
        try:
            async with httpx.AsyncClient(timeout=timeout, follow_redirects=True,
                                         verify=False, proxy=proxy) as c:
                resp = await c.get(url, params=params, headers=h)
                # 429/403 = rate-limited / WAF; back off and retry, then give up quietly.
                if resp.status_code in (403, 429):
                    if attempt < 3:
                        await asyncio.sleep(int(resp.headers.get("Retry-After", 3 * (attempt + 1))))
                    continue
                resp.raise_for_status()
                return resp.text
        except (httpx.TimeoutException, httpx.RemoteProtocolError, httpx.ConnectError, httpx.HTTPStatusError):
            if attempt < 3:
                await asyncio.sleep(2 ** attempt)
    return ""


def parse_date(value: str | int | float | None) -> str:
    """Parse any date-ish value to ISO 8601 string. Returns empty string on failure."""
    if not value:
        return ""
    try:
        # Unix timestamp (seconds or ms)
        if isinstance(value, (int, float)):
            ts = value / 1000 if value > 1e10 else value
            return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()
        s = str(value).strip()
        # Relative ("2 days ago", "3 hours ago")
        m = re.match(r"(\d+)\s+(second|minute|hour|day|week|month)s?\s+ago", s, re.I)
        if m:
            n, unit = int(m.group(1)), m.group(2).lower()
            delta = {"second": 1, "minute": 60, "hour": 3600, "day": 86400,
                     "week": 604800, "month": 2592000}[unit]
            return (datetime.now(tz=timezone.utc) - timedelta(seconds=n * delta)).isoformat()
        # ISO / RFC / common formats
        for fmt in ("%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%d",
                    "%a, %d %b %Y %H:%M:%S %z", "%B %d, %Y", "%d %b %Y"):
            try:
                return datetime.strptime(s[:25], fmt).isoformat()
            except ValueError:
                pass
        return s
    except Exception:
        return ""


def is_recent(date_str: str) -> bool:
    # Empty date → keep it (HN and some aggregators legitimately don't supply
    # a posted_date; rejecting all of them is too aggressive).
    # Malformed date → reject (a scraper returning garbage shouldn't sneak
    # stale postings through silently).
    if not date_str:
        return True
    try:
        dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return (datetime.now(tz=timezone.utc) - dt).days <= MAX_AGE_DAYS
    except Exception:
        return False


def strip_html(text: str) -> str:
    text = re.sub(r"<br\s*/?>|<p\s*/?>|<li\s*/?>", "\n", text, flags=re.I)
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"&amp;", "&", text)
    text = re.sub(r"&lt;", "<", text)
    text = re.sub(r"&gt;", ">", text)
    text = re.sub(r"&nbsp;", " ", text)
    text = re.sub(r"&#\d+;", " ", text)
    return re.sub(r"\n{3,}", "\n\n", text).strip()

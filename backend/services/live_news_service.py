from __future__ import annotations

from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any, Dict, List
from urllib.request import Request, urlopen
import html
import re
import time
import xml.etree.ElementTree as ET

import httpx


# Real, topic-specific feeds. No route/port filtering is used.
RSS_FEEDS = [
    {
        "url": "https://feeds.feedburner.com/gcaptain",
        "source": "gCaptain",
        "category": "MARITIME",
        "topics": {"maritime", "freight", "weather"},
    },
    {
        "url": "https://www.marinelink.com/news/rss",
        "source": "MarineLink",
        "category": "MARITIME",
        "topics": {"maritime", "freight"},
    },
    {
        "url": "https://cap-sources.s3.amazonaws.com/in-imd-en/rss.xml",
        "source": "IMD / India CAP",
        "category": "WEATHER",
        "topics": {"weather"},
    },
    {
        "url": "https://www.nhc.noaa.gov/xml/TWDAT.xml",
        "source": "NOAA / NHC",
        "category": "WEATHER",
        "topics": {"weather"},
    },
]

# Google News RSS is used for broad freight-market coverage.
GOOGLE_QUERIES = [
    ("Baltic Dry Index shipping freight", "FREIGHT"),
    ("dry bulk freight rates Capesize Panamax Supramax", "FREIGHT"),
    ("bulk carrier charter rates shipping market", "FREIGHT"),
    ("maritime shipping vessel sea news", "MARITIME"),
    ("marine weather storm cyclone shipping", "WEATHER"),
    ("Bay of Bengal Arabian Sea marine weather", "WEATHER"),
]

_CACHE: Dict[str, tuple[float, Dict[str, Any]]] = {}
CACHE_SECONDS = 180


def _clean(value: Any) -> str:
    text = html.unescape(str(value or ""))
    return re.sub(r"\s+", " ", text).strip()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _date(value: str) -> str:
    value = _clean(value)
    if not value:
        return _now()
    try:
        return parsedate_to_datetime(value).isoformat()
    except Exception:
        return value


def _topic_tags(title: str) -> List[str]:
    text = title.lower()
    tags: List[str] = []

    if any(x in text for x in (
        "baltic dry", "freight", "capesize", "panamax", "supramax",
        "handysize", "bulk carrier", "charter", "dry bulk", "bunker",
        "marine fuel", "vlsfo",
    )):
        tags.append("FREIGHT")

    if any(x in text for x in (
        "maritime", "shipping", "vessel", "ship", "ocean",
        "seas", "sea route", "fleet", "merchant",
    )):
        tags.append("MARITIME")

    if any(x in text for x in (
        "weather", "cyclone", "storm", "monsoon", "rough seas",
        "high waves", "typhoon", "tropical", "warning",
        "bay of bengal", "arabian sea", "indian ocean",
        "wind", "rainfall",
    )):
        tags.append("WEATHER")

    if any(x in text for x in (
        "strike", "sanction", "conflict", "war", "attack",
        "blockade", "closure", "disruption", "delay", "security",
    )):
        tags.append("RISK")

    return list(dict.fromkeys(tags)) or ["MARITIME"]


def _parse_rss(xml_bytes: bytes, default_source: str, default_category: str) -> List[Dict[str, Any]]:
    root = ET.fromstring(xml_bytes)
    items: List[Dict[str, Any]] = []

    # RSS 2.0
    rss_items = root.findall(".//item")

    # Atom fallback
    if not rss_items:
        ns = {"atom": "http://www.w3.org/2005/Atom"}
        entries = root.findall(".//atom:entry", ns)
        for entry in entries:
            title = _clean(entry.findtext("atom:title", namespaces=ns))
            link_el = entry.find("atom:link", ns)
            link = _clean(link_el.get("href") if link_el is not None else "")
            published = _clean(
                entry.findtext("atom:published", namespaces=ns)
                or entry.findtext("atom:updated", namespaces=ns)
            )

            if title and link:
                items.append({
                    "title": title,
                    "url": link,
                    "published": _date(published),
                    "source": default_source,
                    "domain": default_source,
                    "category": default_category,
                })
        return items

    for item in rss_items:
        title = _clean(item.findtext("title"))
        link = _clean(item.findtext("link"))
        pub = _clean(item.findtext("pubDate") or item.findtext("published"))
        source_el = item.find("source")
        source = _clean(source_el.text if source_el is not None else "") or default_source

        if not title or not link:
            continue

        items.append({
            "title": title,
            "url": link,
            "published": _date(pub),
            "source": source,
            "domain": source,
            "category": default_category,
        })

    return items


def _fetch_url(url: str, timeout: float = 10.0) -> bytes:
    req = Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X) FreightOne/1.0",
            "Accept": "application/rss+xml, application/atom+xml, application/xml, text/xml, */*",
        },
    )
    with urlopen(req, timeout=timeout) as response:
        return response.read()


def _fetch_google(query: str, timeout: float = 10.0) -> List[Dict[str, Any]]:
    from urllib.parse import quote_plus

    url = (
        "https://news.google.com/rss/search"
        f"?q={quote_plus(query)}&hl=en-IN&gl=IN&ceid=IN:en"
    )

    raw = _fetch_url(url, timeout)
    return _parse_rss(raw, "Google News", "MARKET")


def _normalise(item: Dict[str, Any]) -> Dict[str, Any]:
    title = _clean(item.get("title"))
    source = _clean(item.get("source") or item.get("domain") or "News")
    tags = _topic_tags(title)

    category = item.get("category")
    if "WEATHER" in tags:
        category = "WEATHER"
    elif "FREIGHT" in tags:
        category = "FREIGHT"
    else:
        category = category or "MARITIME"

    return {
        "title": title,
        "url": item.get("url", ""),
        "published": item.get("published", _now()),
        "domain": source,
        "source": source,
        "category": category,
        "tags": tags + ["LIVE"],
        "live": True,
    }


def _dedupe(items: List[Dict[str, Any]], limit: int) -> List[Dict[str, Any]]:
    seen = set()
    output = []
    for item in items:
        key = item.get("url") or item.get("title")
        if not key or key in seen:
            continue
        seen.add(key)
        output.append(_normalise(item))
        if len(output) >= limit:
            break
    return output


def fetch_live_news(
    *,
    material: str | None = None,
    origin: str | None = None,
    port: str | None = None,
    timespan: str = "24h",
    maxrecords: int = 10,
    timeout: float = 10.0,
) -> Dict[str, Any]:
    """
    Global live intelligence feed. material/origin/port are retained only
    because the existing FastAPI endpoint passes them; they are intentionally
    NOT used to filter news.

    Source priority:
      1. Direct publisher/government RSS feeds
      2. Google News RSS topic queries
    """

    key = "global-maritime-freight-weather"

    cached = _CACHE.get(key)
    if cached and time.time() - cached[0] < CACHE_SECONDS:
        result = dict(cached[1])
        result["cached"] = True
        return result

    items: List[Dict[str, Any]] = []
    errors: List[str] = []

    # Direct source feeds first. This avoids depending on GDELT's rate limit.
    for feed in RSS_FEEDS:
        try:
            raw = _fetch_url(feed["url"], timeout)
            parsed = _parse_rss(raw, feed["source"], feed["category"])

            for item in parsed:
                tags = _topic_tags(item["title"])
                if feed["category"] == "WEATHER" and "WEATHER" not in tags:
                    tags.append("WEATHER")

                item["category"] = feed["category"]
                items.append(item)

        except Exception as exc:
            errors.append(f"{feed['source']}: {exc}")

    # Google News RSS supplements freight-specific coverage.
    for query, category in GOOGLE_QUERIES:
        if len(_dedupe(items, maxrecords)) >= maxrecords:
            break

        try:
            parsed = _fetch_google(query, timeout)
            for item in parsed:
                item["category"] = category
                items.append(item)
        except Exception as exc:
            errors.append(f"Google News '{query}': {exc}")

    final = _dedupe(items, maxrecords)

    if final:
        result = {
            "items": final,
            "live": True,
            "source": "Direct maritime/weather RSS + Google News RSS",
            "updated_at": _now(),
            "error": None,
            "cached": False,
            "scope": "Global freight, maritime and marine-weather intelligence",
        }
        _CACHE[key] = (time.time(), result)
        return result

    return {
        "items": [],
        "live": False,
        "source": "Live feeds unavailable",
        "updated_at": _now(),
        "error": "; ".join(errors) or "All live sources returned no items.",
        "cached": False,
        "scope": "Global freight, maritime and marine-weather intelligence",
    }


# Existing main.py imports this exact name.

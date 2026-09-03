"""Trending news sources beyond Hacker News.

Every scraper returns a list[dict] with the same shape as `hacker_news.py`:
    { id, title, url, score, comments, by, time }

`score` and `comments` are normalised as best-effort — for RSS feeds without
engagement metrics we synthesise a default score based on source authority
so the downstream ranker can still order them.

Sources included:
- Techmeme RSS  → the definitive "what everyone is talking about" aggregator
- Reddit JSON   → r/technology, r/programming, r/LocalLLaMA, r/MachineLearning,
                  r/selfhosted (hot last 24h with score threshold)
- The Verge RSS → mainstream tech news with strong hooks
- TechCrunch RSS → funding, launches, corporate drama
- 404 Media RSS → original investigative tech scoops
- BleepingComputer RSS → cybersecurity breaking news

None of these need auth or API keys.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import re
import time
from typing import Any
from xml.etree import ElementTree as ET

import httpx

logger = logging.getLogger(__name__)

_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36 "
    "JobHunter/1.0 (+https://github.com/jv-maroto/jobhunter-oss)"
)
_HEADERS = {"User-Agent": _USER_AGENT, "Accept": "*/*"}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _stable_id(url: str) -> int:
    """Deterministic positive int id from URL, so dedupe across sources works."""
    h = hashlib.blake2b(url.encode("utf-8"), digest_size=6).hexdigest()
    return int(h, 16)


def _clean_html(text: str) -> str:
    """Strip HTML tags and collapse whitespace for RSS summaries."""
    text = re.sub(r"<[^>]+>", " ", text or "")
    return re.sub(r"\s+", " ", text).strip()


def _parse_rfc822(date_str: str) -> int:
    """RSS pubDate → unix timestamp. Returns 0 on parse failure."""
    if not date_str:
        return 0
    try:
        from email.utils import parsedate_to_datetime
        return int(parsedate_to_datetime(date_str).timestamp())
    except Exception:  # noqa: BLE001
        return 0


async def _fetch_rss(
    client: httpx.AsyncClient, url: str, source_name: str
) -> list[dict[str, Any]]:
    """Parse an RSS 2.0 / Atom feed. Returns items with normalised shape."""
    try:
        r = await client.get(url, headers=_HEADERS, timeout=15.0, follow_redirects=True)
        r.raise_for_status()
        root = ET.fromstring(r.text)
    except Exception as exc:  # noqa: BLE001
        logger.warning("RSS fetch failed for %s: %s", source_name, exc)
        return []

    # RSS 2.0 vs Atom differ in structure — handle both.
    items: list[dict[str, Any]] = []
    # RSS 2.0 items
    for it in root.iter("item"):
        title = (it.findtext("title") or "").strip()
        link = (it.findtext("link") or "").strip()
        pub = it.findtext("pubDate") or ""
        desc = it.findtext("description") or ""
        if not title or not link:
            continue
        items.append({
            "id": _stable_id(link),
            "title": title,
            "url": link,
            "score": 0,  # will be filled by the caller (source-authority weight)
            "comments": 0,
            "by": source_name,
            "time": _parse_rfc822(pub),
            "summary_raw": _clean_html(desc),
        })
    # Atom entries
    if not items:
        ns = {"atom": "http://www.w3.org/2005/Atom"}
        for entry in root.iter("{http://www.w3.org/2005/Atom}entry"):
            title = (entry.findtext("atom:title", namespaces=ns) or "").strip()
            link_el = entry.find("atom:link", namespaces=ns)
            link = link_el.get("href") if link_el is not None else ""
            pub = (
                entry.findtext("atom:published", namespaces=ns)
                or entry.findtext("atom:updated", namespaces=ns)
                or ""
            )
            summary = (entry.findtext("atom:summary", namespaces=ns) or "").strip()
            if not title or not link:
                continue
            # Parse ISO-8601 for Atom
            try:
                from datetime import datetime
                ts = int(datetime.fromisoformat(pub.replace("Z", "+00:00")).timestamp())
            except Exception:  # noqa: BLE001
                ts = 0
            items.append({
                "id": _stable_id(link),
                "title": title,
                "url": link,
                "score": 0,
                "comments": 0,
                "by": source_name,
                "time": ts,
                "summary_raw": _clean_html(summary),
            })
    return items


# ---------------------------------------------------------------------------
# Techmeme — the gold standard aggregator
# ---------------------------------------------------------------------------
async def fetch_techmeme_24h(
    client: httpx.AsyncClient, limit: int = 30
) -> list[dict[str, Any]]:
    """Techmeme surfaces stories that ALL tech outlets are covering at once —
    the closest signal to 'what's in everyone's mouth right now'."""
    items = await _fetch_rss(client, "https://www.techmeme.com/feed.xml", "techmeme")
    cutoff = int(time.time()) - 24 * 3600
    # Techmeme items are always fresh (last few hours), but filter defensively
    fresh = [it for it in items if it["time"] == 0 or it["time"] >= cutoff]
    # Source authority: Techmeme is highly curated → give a solid baseline score
    for it in fresh:
        it["score"] = 500  # baseline high — will be re-ranked with other signals
    return fresh[:limit]


# ---------------------------------------------------------------------------
# Reddit — hot subreddits with score threshold
# ---------------------------------------------------------------------------
_REDDIT_SUBS = [
    "technology",
    "programming",
    "LocalLLaMA",
    "MachineLearning",
    "selfhosted",
    "webdev",
]


_REDDIT_UA = "python:jobhunter:1.0 (by /u/jobhunter-oss)"
_REDDIT_HEADERS = {"User-Agent": _REDDIT_UA, "Accept": "application/json"}


async def _fetch_reddit_sub(
    client: httpx.AsyncClient, sub: str, min_score: int = 500
) -> list[dict[str, Any]]:
    """Reddit's public JSON API. Hot posts of last 24h with high engagement.
    Reddit blocks generic UAs — use the format they publicly document."""
    # old.reddit.com sometimes accepts requests that www.reddit.com blocks
    for host in ("old.reddit.com", "www.reddit.com"):
        url = f"https://{host}/r/{sub}/top.json?t=day&limit=25"
        try:
            r = await client.get(url, headers=_REDDIT_HEADERS, timeout=15.0)
            r.raise_for_status()
            data = r.json()
            break
        except Exception as exc:  # noqa: BLE001
            if host == "www.reddit.com":
                logger.warning("Reddit fetch failed for r/%s: %s", sub, exc)
                return []
            # else try the next host
            continue

    posts: list[dict[str, Any]] = []
    for entry in data.get("data", {}).get("children", []):
        p = entry.get("data", {})
        if p.get("stickied") or p.get("over_18"):
            continue
        score = int(p.get("score", 0) or 0)
        if score < min_score:
            continue
        # Prefer external link, fall back to reddit permalink for self-posts
        url = (p.get("url") or "").strip()
        permalink = f"https://www.reddit.com{p.get('permalink', '')}"
        if url.startswith("https://www.reddit.com") or not url.startswith("http"):
            url = permalink
        title = (p.get("title") or "").strip()
        if not title or not url:
            continue
        posts.append({
            "id": _stable_id(url),
            "title": title,
            "url": url,
            "score": score,
            "comments": int(p.get("num_comments", 0) or 0),
            "by": f"reddit/r/{sub}",
            "time": int(p.get("created_utc", 0) or 0),
            "summary_raw": (p.get("selftext") or "")[:280],
        })
    return posts


async def fetch_reddit_24h(
    client: httpx.AsyncClient, limit: int = 40
) -> list[dict[str, Any]]:
    """Aggregates top posts of last 24h across 6 tech subreddits with score>500."""
    per_sub = await asyncio.gather(
        *(_fetch_reddit_sub(client, sub) for sub in _REDDIT_SUBS),
        return_exceptions=True,
    )
    all_posts: list[dict[str, Any]] = []
    for res in per_sub:
        if isinstance(res, list):
            all_posts.extend(res)
    all_posts.sort(key=lambda x: x["score"], reverse=True)
    return all_posts[:limit]


# ---------------------------------------------------------------------------
# The Verge / TechCrunch / 404 Media / BleepingComputer — pure RSS
# ---------------------------------------------------------------------------
_RSS_FEEDS = [
    ("the-verge", "https://www.theverge.com/rss/index.xml", 400),
    ("techcrunch", "https://techcrunch.com/feed/", 400),
    ("404-media", "https://www.404media.co/rss/", 350),
    ("bleeping-computer", "https://www.bleepingcomputer.com/feed/", 350),
    ("ars-technica", "https://feeds.arstechnica.com/arstechnica/index/", 400),
]


async def fetch_rss_feeds_24h(
    client: httpx.AsyncClient, limit_per_feed: int = 15
) -> list[dict[str, Any]]:
    """Pull recent items (last 48h to be safe on slow feeds) from every RSS
    feed and normalise. Each feed injects its source-authority baseline score."""
    cutoff = int(time.time()) - 48 * 3600
    results = await asyncio.gather(
        *(_fetch_rss(client, url, name) for name, url, _ in _RSS_FEEDS),
        return_exceptions=True,
    )
    out: list[dict[str, Any]] = []
    for (name, _url, baseline), res in zip(_RSS_FEEDS, results, strict=False):
        if not isinstance(res, list):
            continue
        fresh = [it for it in res if it["time"] == 0 or it["time"] >= cutoff]
        for it in fresh[:limit_per_feed]:
            it["score"] = baseline
        out.extend(fresh[:limit_per_feed])
    return out


# ---------------------------------------------------------------------------
# Deduplication + ranking
# ---------------------------------------------------------------------------
_TITLE_NORMALISE = re.compile(r"[^\w\s]", re.UNICODE)


def _title_key(title: str) -> str:
    """Normalise a title for near-duplicate detection across sources."""
    t = _TITLE_NORMALISE.sub(" ", title.lower())
    words = [w for w in t.split() if len(w) > 3]
    # First 6 significant words as the dedupe key
    return " ".join(sorted(words[:6]))


def dedupe_and_rank(
    stories: list[dict[str, Any]], limit: int = 30
) -> list[dict[str, Any]]:
    """Cross-source dedupe by (url, title_key). When the same story appears in
    multiple sources, keep the one with highest raw score AND boost its final
    score by +25% per additional source that covers it (proxy for virality)."""
    by_url: dict[str, dict[str, Any]] = {}
    by_titlekey: dict[str, dict[str, Any]] = {}
    for s in stories:
        url = s.get("url", "")
        tkey = _title_key(s.get("title", ""))
        # Match by URL first
        existing = by_url.get(url) or by_titlekey.get(tkey)
        if existing is not None:
            existing["_coverage"] = existing.get("_coverage", 1) + 1
            existing["_also_by"] = existing.get("_also_by", []) + [s.get("by", "?")]
            if s.get("score", 0) > existing.get("score", 0):
                # Keep the version with higher raw score, preserve coverage
                cov = existing["_coverage"]
                also = existing["_also_by"]
                s["_coverage"] = cov
                s["_also_by"] = also
                by_url[url] = s
                by_titlekey[tkey] = s
            continue
        s["_coverage"] = 1
        s["_also_by"] = []
        by_url[url] = s
        by_titlekey[tkey] = s

    unique = list({id(v): v for v in by_url.values()}.values())
    # Final score = raw_score × (1 + 0.25 × extra_coverage)
    for s in unique:
        extra = max(0, s["_coverage"] - 1)
        s["_final_score"] = int(s.get("score", 0) * (1 + 0.25 * extra))
    unique.sort(key=lambda x: x["_final_score"], reverse=True)
    return unique[:limit]


# ---------------------------------------------------------------------------
# Public orchestrator — replaces fetch_top_hn_24h in the pipeline
# ---------------------------------------------------------------------------
async def fetch_top_trending_24h(limit: int = 20) -> list[dict[str, Any]]:
    """Aggregates last-24h stories from every configured source, dedupes across
    them and returns the top N by composite engagement score.

    Sources:
      - Hacker News (via its own scraper — imported lazily to avoid cycles)
      - Techmeme (RSS)
      - Reddit r/technology + programming + LocalLLaMA + MachineLearning +
        selfhosted + webdev (JSON)
      - The Verge, TechCrunch, 404 Media, BleepingComputer, Ars Technica (RSS)
    """
    from app.scrapers.hacker_news import fetch_top_hn_24h

    async with httpx.AsyncClient(follow_redirects=True) as client:
        hn_task = fetch_top_hn_24h(limit=25)  # HN has its own client
        techmeme_task = fetch_techmeme_24h(client, limit=30)
        reddit_task = fetch_reddit_24h(client, limit=40)
        rss_task = fetch_rss_feeds_24h(client, limit_per_feed=12)

        hn, techmeme, reddit, rss = await asyncio.gather(
            hn_task, techmeme_task, reddit_task, rss_task,
            return_exceptions=True,
        )

    all_stories: list[dict[str, Any]] = []
    for res, tag in (
        (hn, "hn"), (techmeme, "techmeme"), (reddit, "reddit"), (rss, "rss"),
    ):
        if isinstance(res, Exception):
            logger.warning("%s source failed: %s", tag, res)
            continue
        all_stories.extend(res)

    logger.info(
        "trending: raw=%d (hn=%d techmeme=%d reddit=%d rss=%d)",
        len(all_stories),
        len(hn) if isinstance(hn, list) else 0,
        len(techmeme) if isinstance(techmeme, list) else 0,
        len(reddit) if isinstance(reddit, list) else 0,
        len(rss) if isinstance(rss, list) else 0,
    )

    ranked = dedupe_and_rank(all_stories, limit=limit)
    logger.info(
        "trending: after dedupe+rank -> %d stories (top3=%s)",
        len(ranked),
        [(s["title"][:60], s["_final_score"], s["_coverage"]) for s in ranked[:3]],
    )
    return ranked

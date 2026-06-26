"""Fetch top Hacker News stories from the last 24h, filtered for tech relevance.

Uses the official HN REST API (no auth, no rate limits).
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

import httpx

logger = logging.getLogger(__name__)

HN_TOP = "https://hacker-news.firebaseio.com/v0/topstories.json"
HN_ITEM = "https://hacker-news.firebaseio.com/v0/item/{id}.json"

# Tech keywords for filtering HN stories — customize for your stack focus
TECH_KEYWORDS = {
    # Python ecosystem
    "python", "fastapi", "django", "flask", "celery", "pydantic", "uv ",
    "pytorch", "numpy", "pandas",
    # AI / LLMs
    "ai ", " ai", "llm", "gpt", "claude", "anthropic", "openai", "llama",
    "mistral", "ollama", "rag", "embedding", "agent", "agents",
    # Frontend
    "react", "vue", "nextjs", "next.js", "typescript", "tailwind", "svelte",
    # DevOps / SysAdmin
    "docker", "kubernetes", "k8s", "helm", "terraform", "ansible",
    "linux", "bash", "ssh", "devops", "sre", "active directory",
    # Databases
    "postgres", "sqlite", "redis", "mongodb", "pgvector", "vector db",
    # Tools / platforms
    "github", "gitlab", "vscode", "neovim", "cli", "open source",
    # Languages of interest
    "rust", "golang", " go ",
    # Cloud / infra
    "aws", "gcp", "cloudflare", "vercel", "render", "fly.io",
    # Security
    "vulnerability", "cve", "security", "exploit",
}


async def fetch_top_hn_24h(limit: int = 10, max_candidates: int = 80) -> list[dict[str, Any]]:
    """Returns top N tech-relevant HN stories from the last 24 hours."""
    cutoff = int(time.time()) - 24 * 3600

    async with httpx.AsyncClient(timeout=10.0) as client:
        ids_resp = await client.get(HN_TOP)
        ids_resp.raise_for_status()
        ids: list[int] = ids_resp.json()[:max_candidates]

        async def fetch_item(sid: int) -> dict[str, Any] | None:
            try:
                r = await client.get(HN_ITEM.format(id=sid))
                r.raise_for_status()
                return r.json()
            except Exception:  # noqa: BLE001
                return None

        items = await asyncio.gather(*(fetch_item(i) for i in ids))

    candidates: list[dict[str, Any]] = []
    for it in items:
        if not it or it.get("type") != "story":
            continue
        if not it.get("title") or it.get("dead") or it.get("deleted"):
            continue
        if (it.get("time") or 0) < cutoff:
            continue
        title = (it.get("title") or "").lower()
        url = (it.get("url") or "").lower()
        blob = f" {title} {url} "
        if not any(kw in blob for kw in TECH_KEYWORDS):
            continue
        candidates.append({
            "id": it["id"],
            "title": it["title"],
            "url": it.get("url") or f"https://news.ycombinator.com/item?id={it['id']}",
            "score": it.get("score", 0),
            "comments": it.get("descendants", 0),
            "by": it.get("by", ""),
            "time": it.get("time", 0),
        })

    # Sort by score DESC, take top N
    candidates.sort(key=lambda x: x["score"], reverse=True)
    top = candidates[:limit]
    logger.info("HN fetched %d candidates, returning top %d", len(candidates), len(top))
    return top

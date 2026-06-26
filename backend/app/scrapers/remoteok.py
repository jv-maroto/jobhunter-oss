"""Scraper RemoteOK - API JSON publica."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

import httpx

from app.scrapers.base import BaseScraper
from app.schemas.job import ScrapedJob

logger = logging.getLogger(__name__)

RELEVANT_TAGS = {
    "python",
    "fastapi",
    "django",
    "react",
    "typescript",
    "javascript",
    "devops",
    "backend",
    "fullstack",
    "full-stack",
    "ai",
    "machine-learning",
    "ml",
    "docker",
    "sql",
    "postgres",
    "linux",
    "sysadmin",
    "sre",
    "api",
}


class RemoteOkScraper(BaseScraper):
    name = "remoteok"
    url = "https://remoteok.com/api"

    async def fetch(self) -> list[ScrapedJob]:
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
            ),
            "Accept": "application/json",
        }
        jobs: list[ScrapedJob] = []
        try:
            async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
                resp = await client.get(self.url, headers=headers)
                resp.raise_for_status()
                data = resp.json()
        except Exception as exc:  # noqa: BLE001
            logger.warning("remoteok fetch failed: %s", exc)
            return []

        if not isinstance(data, list):
            return []

        for entry in data:
            if not isinstance(entry, dict) or "position" not in entry:
                continue
            tags = [str(t).lower() for t in entry.get("tags", [])]
            if not any(t in RELEVANT_TAGS for t in tags):
                # Aun asi lo dejamos si parece tech generico.
                if not any(
                    kw in (entry.get("position", "") or "").lower()
                    for kw in ("python", "develop", "engineer", "backend", "fullstack", "devops")
                ):
                    continue

            posted = entry.get("date")
            try:
                posted_dt = (
                    datetime.fromisoformat(posted.replace("Z", "+00:00"))
                    if isinstance(posted, str)
                    else None
                )
            except Exception:  # noqa: BLE001
                posted_dt = None

            jobs.append(
                ScrapedJob(
                    source=self.name,
                    source_id=str(entry.get("id", "")),
                    source_url=entry.get("url", "") or entry.get("apply_url", ""),
                    title=entry.get("position", "") or entry.get("title", ""),
                    company=entry.get("company", "") or "Unknown",
                    location=entry.get("location", "") or "Remote",
                    remote=True,
                    salary_min=float(entry["salary_min"]) if entry.get("salary_min") else None,
                    salary_max=float(entry["salary_max"]) if entry.get("salary_max") else None,
                    currency="USD",
                    posted_at=posted_dt or datetime.now(tz=timezone.utc),
                    description=entry.get("description", "")[:8000],
                    tags=tags,
                )
            )

        return self._finalize(jobs)

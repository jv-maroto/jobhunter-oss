"""Scraper Remotive - API JSON publica."""

from __future__ import annotations

import logging
from datetime import datetime

import httpx

from app.schemas.job import ScrapedJob
from app.scrapers.base import BaseScraper

logger = logging.getLogger(__name__)

SEARCH_TERMS = ["python", "fastapi", "devops", "ai engineer", "full stack"]
BASE_URL = "https://remotive.com/api/remote-jobs"


class RemotiveScraper(BaseScraper):
    name = "remotive"

    async def fetch(self) -> list[ScrapedJob]:
        jobs: list[ScrapedJob] = []
        seen_ids: set[str] = set()

        try:
            async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
                for term in SEARCH_TERMS:
                    try:
                        resp = await client.get(
                            BASE_URL,
                            params={"category": "software-dev", "search": term},
                        )
                        resp.raise_for_status()
                        data = resp.json()
                    except Exception as exc:  # noqa: BLE001
                        logger.warning("remotive term=%s failed: %s", term, exc)
                        continue

                    for entry in data.get("jobs", []):
                        sid = str(entry.get("id", ""))
                        if sid in seen_ids:
                            continue
                        seen_ids.add(sid)

                        posted = entry.get("publication_date")
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
                                source_id=sid,
                                source_url=entry.get("url", ""),
                                title=entry.get("title", ""),
                                company=entry.get("company_name", "Unknown"),
                                location=entry.get("candidate_required_location", "Remote"),
                                remote=True,
                                salary_min=None,
                                salary_max=None,
                                currency=None,
                                posted_at=posted_dt,
                                description=entry.get("description", "")[:8000],
                                tags=[t.lower() for t in entry.get("tags", [])],
                            )
                        )
        except Exception as exc:  # noqa: BLE001
            logger.warning("remotive client failed: %s", exc)
            return []

        return self._finalize(jobs)

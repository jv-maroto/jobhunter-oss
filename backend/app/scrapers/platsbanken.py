"""Scraper Platsbanken (Suecia) via la JobTech Search API.

API publica oficial de Arbetsformedlingen, SIN autenticacion (ToS bajo).
Solo se activa cuando el usuario incluye Suecia (SE) en sus regiones; de eso se
encarga el registry/catalogo, no este scraper.
"""

from __future__ import annotations

import logging
from datetime import datetime

import httpx

from app.scrapers.base import BaseScraper
from app.schemas.job import ScrapedJob

logger = logging.getLogger(__name__)

BASE_URL = "https://jobsearch.api.jobtechdev.se/search"
QUERIES = ["python", "developer", "devops", "fullstack", "data engineer"]


class PlatsbankenScraper(BaseScraper):
    name = "platsbanken"

    async def fetch(self) -> list[ScrapedJob]:
        jobs: list[ScrapedJob] = []
        seen: set[str] = set()
        headers = {"accept": "application/json", "User-Agent": "jobhunter"}
        try:
            async with httpx.AsyncClient(timeout=30.0, headers=headers, follow_redirects=True) as client:
                for q in QUERIES:
                    try:
                        resp = await client.get(BASE_URL, params={"q": q, "limit": 25})
                        resp.raise_for_status()
                        data = resp.json()
                    except Exception as exc:  # noqa: BLE001
                        logger.warning("platsbanken q=%s failed: %s", q, exc)
                        continue

                    for hit in data.get("hits", []):
                        sid = str(hit.get("id", ""))
                        if not sid or sid in seen:
                            continue
                        seen.add(sid)

                        employer = (hit.get("employer") or {}).get("name") or "Unknown"
                        addr = hit.get("workplace_address") or {}
                        loc = addr.get("municipality") or addr.get("region") or "Sweden"
                        url = hit.get("webpage_url") or (hit.get("application_details") or {}).get("url") or ""

                        posted = hit.get("publication_date")
                        try:
                            posted_dt = (
                                datetime.fromisoformat(posted.replace("Z", "+00:00"))
                                if isinstance(posted, str)
                                else None
                            )
                        except Exception:  # noqa: BLE001
                            posted_dt = None

                        remote = bool(hit.get("remote_work")) or "distans" in str(loc).lower()

                        jobs.append(
                            ScrapedJob(
                                source=self.name,
                                source_id=sid,
                                source_url=url,
                                title=str(hit.get("headline", "") or ""),
                                company=str(employer),
                                location=str(loc),
                                remote=remote,
                                posted_at=posted_dt,
                                description=str((hit.get("description") or {}).get("text", "") or "")[:8000],
                                tags=[q, "SE"],
                            )
                        )
        except Exception as exc:  # noqa: BLE001
            logger.warning("platsbanken client failed: %s", exc)
            return []

        return self._finalize(jobs)

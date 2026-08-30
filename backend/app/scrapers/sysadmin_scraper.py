"""Scraper de ofertas sysadmin/devops/sre via jobspy, con queries fijas.

SOLO se usa en modo legacy (instalacion sin onboarding completado). Una vez
tienes perfil, `query_builder` genera las busquedas a partir de TUS roles y
skills, que es lo que quieres: estas queries son un punto de partida generico,
no un perfil concreto.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

from app.schemas.job import ScrapedJob
from app.scrapers.base import BaseScraper

logger = logging.getLogger(__name__)

SYSADMIN_QUERIES = [
    "senior linux administrator remote",
    "devops engineer remote europe",
    "site reliability engineer remote",
    "infrastructure engineer remote",
    "cloud engineer aws remote",
    "platform engineer kubernetes remote",
    "system administrator senior remote",
    "ingeniero sistemas devops remoto",
    "administrador sistemas linux senior",
]


class SysAdminScraper(BaseScraper):
    """jobspy-backed scraper with sysadmin-oriented queries."""

    name = "jobspy-sysadmin"

    async def fetch(self) -> list[ScrapedJob]:
        try:
            return await asyncio.to_thread(self._fetch_sync)
        except Exception as exc:  # noqa: BLE001
            logger.warning("sysadmin scraper failed: %s", exc)
            return []

    def _fetch_sync(self) -> list[ScrapedJob]:
        try:
            from jobspy import scrape_jobs  # type: ignore[import-not-found]
        except Exception as exc:  # noqa: BLE001
            logger.warning("jobspy not installed: %s", exc)
            return []

        all_jobs: list[ScrapedJob] = []
        for query in SYSADMIN_QUERIES:
            try:
                df = scrape_jobs(
                    site_name=["linkedin", "indeed"],
                    search_term=query,
                    location="Spain",
                    results_wanted=15,
                    hours_old=48,
                    country_indeed="Spain",
                    verbose=0,
                )
            except Exception as exc:  # noqa: BLE001
                logger.warning("sysadmin query=%s failed: %s", query, exc)
                continue
            if df is None or len(df) == 0:
                continue
            for _, row in df.iterrows():
                title = str(row.get("title", "") or "")
                company = str(row.get("company", "") or "")
                if not title or not company:
                    continue
                site = str(row.get("site", "") or "jobspy-sysadmin")
                jurl = str(row.get("job_url", "") or row.get("job_url_direct", "") or "")
                loc = str(row.get("location", "") or "")
                remote = bool(row.get("is_remote", False))
                sal_min = row.get("min_amount")
                sal_max = row.get("max_amount")
                currency = row.get("currency", "EUR")

                posted = row.get("date_posted")
                if isinstance(posted, str):
                    try:
                        posted_dt = datetime.fromisoformat(posted)
                    except Exception:  # noqa: BLE001
                        posted_dt = datetime.now(tz=timezone.utc)
                else:
                    try:
                        posted_dt = (
                            posted.to_pydatetime() if hasattr(posted, "to_pydatetime") else None
                        )
                    except Exception:  # noqa: BLE001
                        posted_dt = None

                all_jobs.append(
                    ScrapedJob(
                        source=site or self.name,
                        source_url=jurl,
                        title=title,
                        company=company,
                        location=loc,
                        remote=remote,
                        salary_min=float(sal_min) if sal_min else None,
                        salary_max=float(sal_max) if sal_max else None,
                        currency=currency or "EUR",
                        posted_at=posted_dt,
                        description=str(row.get("description", "") or "")[:8000],
                        tags=[query, "sysadmin-track"],
                    )
                )
        return self._finalize(all_jobs)

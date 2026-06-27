"""Scraper LinkedIn/Indeed/Glassdoor/Google via python-jobspy.

Antes tenia las queries y el pais hardcodeados. Ahora acepta una lista de
`JobspyPlan` (construidos por `registry.build_active_scrapers` a partir de las
preferencias del usuario). Si no se pasan planes, usa el plan LEGACY (mismas
queries y `Spain` de siempre), de modo que el comportamiento por defecto no
cambia para una instalacion sin configurar.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone

from app.scrapers.base import BaseScraper
from app.schemas.job import ScrapedJob

logger = logging.getLogger(__name__)

# Comportamiento legacy (instalacion sin configurar): identico al original.
SEARCH_QUERIES = [
    "python developer remote",
    "fastapi",
    "ai engineer junior",
    "devops junior",
    "full stack python",
]


@dataclass
class JobspyPlan:
    """Un grupo de busqueda jobspy: sitios + queries + ubicacion.

    `country_indeed=None` y `location=""` => busqueda sin pais (remoto).
    Si `sites` incluye "google", se pasa `google_search_term`.
    """

    sites: list[str]
    queries: list[str]
    location: str = "Spain"
    country_indeed: str | None = "Spain"
    results_wanted: int = 20
    hours_old: int = 24
    extra_tags: list[str] = field(default_factory=list)


def _legacy_plan() -> JobspyPlan:
    return JobspyPlan(
        sites=["linkedin", "indeed", "glassdoor"],
        queries=list(SEARCH_QUERIES),
        location="Spain",
        country_indeed="Spain",
        results_wanted=20,
        hours_old=24,
    )


class JobspyScraper(BaseScraper):
    """Wrapper sobre python-jobspy. Sincrono internamente, lo movemos a thread."""

    name = "jobspy"

    def __init__(self, plans: list[JobspyPlan] | None = None) -> None:
        # None => plan legacy (retrocompatible con `JobspyScraper()`).
        self._plans = plans

    async def fetch(self) -> list[ScrapedJob]:
        try:
            return await asyncio.to_thread(self._fetch_sync)
        except Exception as exc:  # noqa: BLE001
            logger.warning("jobspy failed: %s", exc)
            return []

    def _fetch_sync(self) -> list[ScrapedJob]:
        try:
            from jobspy import scrape_jobs  # type: ignore[import-not-found]
        except Exception as exc:  # noqa: BLE001
            logger.warning("jobspy not installed: %s", exc)
            return []

        plans = self._plans if self._plans is not None else [_legacy_plan()]
        all_jobs: list[ScrapedJob] = []

        for plan in plans:
            for query in plan.queries:
                kwargs: dict = {
                    "site_name": plan.sites,
                    "search_term": query,
                    "location": plan.location or None,
                    "results_wanted": plan.results_wanted,
                    "hours_old": plan.hours_old,
                    "verbose": 0,
                }
                if plan.country_indeed:
                    kwargs["country_indeed"] = plan.country_indeed
                if "google" in plan.sites:
                    kwargs["google_search_term"] = query
                try:
                    df = scrape_jobs(**kwargs)
                except Exception as exc:  # noqa: BLE001
                    logger.warning("jobspy query=%s loc=%s failed: %s", query, plan.location, exc)
                    continue

                if df is None or len(df) == 0:
                    continue

                tags_base = [query, *plan.extra_tags]
                for _, row in df.iterrows():
                    title = str(row.get("title", "") or "")
                    company = str(row.get("company", "") or "")
                    if not title or not company:
                        continue
                    site = str(row.get("site", "") or "jobspy")
                    jurl = str(row.get("job_url", "") or row.get("job_url_direct", "") or "")
                    loc = str(row.get("location", "") or "")
                    remote_val = row.get("is_remote", False)
                    remote = bool(remote_val) if remote_val is not None else False

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
                            tags=tags_base,
                        )
                    )

        return self._finalize(all_jobs)

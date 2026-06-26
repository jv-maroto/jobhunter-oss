"""Scraper LinkedIn/Indeed/Glassdoor/ZipRecruiter via python-jobspy."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

from app.scrapers.base import BaseScraper
from app.schemas.job import ScrapedJob

logger = logging.getLogger(__name__)

SEARCH_QUERIES = [
    "python developer remote",
    "fastapi",
    "ai engineer junior",
    "devops junior",
    "full stack python",
]


class JobspyScraper(BaseScraper):
    """Wrapper sobre python-jobspy. Sincrono internamente, lo movemos a thread."""

    name = "jobspy"

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

        all_jobs: list[ScrapedJob] = []
        for query in SEARCH_QUERIES:
            try:
                df = scrape_jobs(
                    site_name=["linkedin", "indeed", "glassdoor"],
                    search_term=query,
                    location="Spain",
                    results_wanted=20,
                    hours_old=24,
                    country_indeed="Spain",
                    verbose=0,
                )
            except Exception as exc:  # noqa: BLE001
                logger.warning("jobspy query=%s failed: %s", query, exc)
                continue

            if df is None or len(df) == 0:
                continue

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
                        tags=[query],
                    )
                )

        return self._finalize(all_jobs)

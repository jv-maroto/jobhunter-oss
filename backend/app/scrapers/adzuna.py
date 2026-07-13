"""Scraper Adzuna — API oficial (clave gratuita).

Es la mejor cobertura por pais de todo el catalogo: ES, GB, DE, FR, NL, IT, PL,
AT, BE... Requiere ADZUNA_APP_ID + ADZUNA_APP_KEY (gratis en
https://developer.adzuna.com). Sin claves, el registry lo desactiva solo via
`requires_env`, asi que nunca aparece como activo sin funcionar.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime

import httpx

from app.config import settings
from app.scrapers.base import BaseScraper
from app.schemas.job import ScrapedJob

logger = logging.getLogger(__name__)

BASE_URL = "https://api.adzuna.com/v1/api/jobs/{country}/search/1"

# Regiones del catalogo -> codigo de pais de Adzuna.
REGION_TO_ADZUNA: dict[str, str] = {
    "ES": "es",
    "GB": "gb",
    "DE": "de",
    "FR": "fr",
    "NL": "nl",
    "IT": "it",
    "PL": "pl",
    "AT": "at",
    "BE": "be",
    "IE": "ie",
    "PT": "pt",
    "SE": "se",
    "CH": "ch",
    "NO": "no",
    "DK": "dk",
}

RESULTS_PER_QUERY = 50
MAX_DAYS_OLD = 7


class AdzunaScraper(BaseScraper):
    name = "adzuna"

    def __init__(self) -> None:
        self._regions: list[str] = ["ES"]
        self._queries: list[str] = ["python developer"]

    def configure(
        self,
        *,
        regions: list[str] | None = None,
        queries: list[str] | None = None,
        prefs: dict | None = None,
    ) -> None:
        if regions:
            # REMOTE no es un pais: Adzuna filtra por pais, no por remoto.
            mapped = [r for r in regions if r in REGION_TO_ADZUNA]
            if mapped:
                self._regions = mapped
        if queries:
            self._queries = queries[:4]  # acotamos: 1 llamada por (pais, query)

    async def _search(
        self, client: httpx.AsyncClient, country: str, query: str
    ) -> list[ScrapedJob]:
        try:
            resp = await client.get(
                BASE_URL.format(country=country),
                params={
                    "app_id": settings.adzuna_app_id,
                    "app_key": settings.adzuna_app_key,
                    "what": query,
                    "results_per_page": RESULTS_PER_QUERY,
                    "max_days_old": MAX_DAYS_OLD,
                    "content-type": "application/json",
                },
            )
            resp.raise_for_status()
            payload = resp.json()
        except Exception as exc:  # noqa: BLE001
            logger.warning("adzuna %s/%r failed: %s", country, query, exc)
            return []

        out: list[ScrapedJob] = []
        for e in payload.get("results", []):
            title = (e.get("title") or "").strip()
            if not title:
                continue

            loc = ((e.get("location") or {}).get("display_name") or "").strip()
            desc = (e.get("description") or "").strip()

            posted_dt = None
            created = e.get("created")
            if isinstance(created, str):
                try:
                    posted_dt = datetime.fromisoformat(created.replace("Z", "+00:00"))
                except ValueError:
                    posted_dt = None

            blob = f"{title} {loc} {desc}".lower()
            out.append(
                ScrapedJob(
                    source=self.name,
                    source_id=str(e.get("id") or ""),
                    source_url=e.get("redirect_url") or "",
                    title=title[:200],
                    company=((e.get("company") or {}).get("display_name") or "Unknown")[:120],
                    location=loc,
                    remote="remote" in blob or "teletrabajo" in blob,
                    salary_min=e.get("salary_min"),
                    salary_max=e.get("salary_max"),
                    currency="EUR" if country != "gb" else "GBP",
                    posted_at=posted_dt,
                    description=desc[:8000],
                    tags=[],
                )
            )
        return out

    async def fetch(self) -> list[ScrapedJob]:
        if not settings.adzuna_app_id or not settings.adzuna_app_key:
            logger.info("adzuna: sin ADZUNA_APP_ID/ADZUNA_APP_KEY, se omite")
            return []

        tasks = []
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            for region in self._regions:
                country = REGION_TO_ADZUNA.get(region)
                if not country:
                    continue
                for q in self._queries:
                    tasks.append(self._search(client, country, q))
            results = await asyncio.gather(*tasks, return_exceptions=True)

        jobs: list[ScrapedJob] = []
        seen: set[str] = set()
        for res in results:
            if isinstance(res, BaseException):
                continue
            for j in res:
                key = j.source_id or j.source_url
                if key in seen:
                    continue
                seen.add(key)
                jobs.append(j)

        return self._finalize(jobs)

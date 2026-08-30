"""Scraper Arbeitnow — API JSON publica, sin auth.

Board europeo (fuerte en DE/AT/NL) con bastante oferta remota y en ingles.
Docs: https://www.arbeitnow.com/api/job-board-api
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

import httpx

from app.schemas.job import ScrapedJob
from app.scrapers.base import BaseScraper

logger = logging.getLogger(__name__)

BASE_URL = "https://www.arbeitnow.com/api/job-board-api"
MAX_PAGES = 3  # ~100 ofertas por pagina

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
    ),
    "Accept": "application/json",
}

# El board trae de todo (enfermeria, logistica, mecatronica...). Filtramos a
# software mirando SOLO el titulo: los `tags` de Arbeitnow son demasiado laxos
# ("engineering" marca ofertas de robotica industrial).
_TECH_HINTS = {
    "software", "developer", "entwickler", "programmer",
    "backend", "back-end", "frontend", "front-end", "fullstack", "full-stack",
    "devops", "sre", "site reliability", "platform engineer", "cloud engineer",
    "data engineer", "data scientist", "machine learning", "ml engineer",
    "python", "java", "javascript", "typescript", "react", "node", "golang",
    "rust", "php", "kubernetes", "linux", "sysadmin", "system administrator",
    "web developer", "mobile developer", "ios", "android", "qa engineer",
}
# Palabras que descartan aunque haya coincidencia (robotica, mecanica...).
_NON_SOFTWARE = {
    "mechatronik", "mechatroniker", "elektroniker", "mechanik",
    "pflege", "krankenschwester", "verkauf", "logistik", "lager",
}


class ArbeitnowScraper(BaseScraper):
    name = "arbeitnow"

    async def fetch(self) -> list[ScrapedJob]:
        jobs: list[ScrapedJob] = []
        seen: set[str] = set()

        try:
            async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
                for page in range(1, MAX_PAGES + 1):
                    try:
                        resp = await client.get(
                            BASE_URL, params={"page": page}, headers=_HEADERS
                        )
                        resp.raise_for_status()
                        payload = resp.json()
                    except Exception as exc:  # noqa: BLE001
                        logger.warning("arbeitnow page=%s failed: %s", page, exc)
                        break

                    entries = payload.get("data") or []
                    if not entries:
                        break

                    for e in entries:
                        slug = str(e.get("slug") or "")
                        if not slug or slug in seen:
                            continue
                        seen.add(slug)

                        title = (e.get("title") or "").strip()
                        low = title.lower()
                        if any(bad in low for bad in _NON_SOFTWARE):
                            continue
                        if not any(h in low for h in _TECH_HINTS):
                            continue

                        created = e.get("created_at")
                        posted_dt = None
                        if isinstance(created, (int, float)):
                            posted_dt = datetime.fromtimestamp(created, tz=timezone.utc)

                        jobs.append(
                            ScrapedJob(
                                source=self.name,
                                source_id=slug,
                                source_url=e.get("url") or "",
                                title=title[:200],
                                company=(e.get("company_name") or "Unknown")[:120],
                                location=(e.get("location") or "").strip(),
                                remote=bool(e.get("remote")),
                                posted_at=posted_dt,
                                description=(e.get("description") or "")[:8000],
                                tags=[str(t).lower() for t in (e.get("tags") or [])][:12],
                            )
                        )
        except Exception as exc:  # noqa: BLE001
            logger.warning("arbeitnow client failed: %s", exc)
            return []

        return self._finalize(jobs)

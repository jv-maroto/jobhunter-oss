"""Interface base para scrapers."""

from __future__ import annotations

import hashlib
import logging
from abc import ABC, abstractmethod

from app.schemas.job import ScrapedJob

logger = logging.getLogger(__name__)


def compute_job_hash(title: str, company: str, location: str = "") -> str:
    """MD5 estable de title+company+location en minusculas."""
    raw = f"{title.strip().lower()}|{company.strip().lower()}|{location.strip().lower()}"
    return hashlib.md5(raw.encode("utf-8")).hexdigest()


class BaseScraper(ABC):
    """Interface comun para todos los scrapers."""

    name: str = "base"

    def configure(
        self,
        *,
        regions: list[str] | None = None,
        queries: list[str] | None = None,
        prefs: dict | None = None,
    ) -> None:
        """Inyecta el contexto de busqueda del usuario (regiones/queries).

        No-op por defecto: los scrapers de un solo board (Remotive, HN...) no lo
        necesitan. Los que si dependen de pais/termino (p.ej. Adzuna) lo
        sobreescriben. El registry lo llama siempre tras instanciar.
        """
        return None

    @abstractmethod
    async def fetch(self) -> list[ScrapedJob]:
        """Devuelve la lista de ofertas encontradas con hash calculado."""

    def _finalize(self, jobs: list[ScrapedJob]) -> list[ScrapedJob]:
        """Garantiza source y hash; loguea totales."""
        out: list[ScrapedJob] = []
        for j in jobs:
            if not j.source:
                j.source = self.name
            if not j.hash:
                j.hash = compute_job_hash(j.title, j.company, j.location)
            out.append(j)
        logger.info("scraper=%s found=%d", self.name, len(out))
        return out

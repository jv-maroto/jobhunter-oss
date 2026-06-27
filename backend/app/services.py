"""Servicios compartidos: cargar CV master, pipeline de scraping->scoring."""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime
from functools import lru_cache
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.models.company import Company
from app.models.job import Job
from app.schemas.job import ScrapedJob, ScoredJobResult
from app.scoring.scorer import score_job
from app.scrapers.registry import build_active_scrapers

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def load_cv_master() -> dict[str, Any]:
    """Carga cv_master.json. Cacheado en memoria."""
    path = settings.cv_master_file
    if not path.exists():
        logger.error("cv_master.json no encontrado en %s", path)
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _get_or_create_company(db: Session, name: str) -> Company | None:
    if not name:
        return None
    existing = db.execute(select(Company).where(Company.name == name)).scalar_one_or_none()
    if existing is not None:
        return existing
    c = Company(name=name)
    db.add(c)
    db.flush()
    return c


def ingest_scraped_jobs(db: Session, scraped: list[ScrapedJob]) -> tuple[int, int]:
    """Inserta ofertas nuevas (dedup por hash). Devuelve (insertados, duplicados)."""
    inserted = 0
    duplicates = 0
    cv = load_cv_master()

    from app.scoring.track_detector import detect_track, predict_salary_band

    def _clean_unicode(s: str | None) -> str | None:
        """Strip lone surrogate halves that SQLite refuses to encode (e.g. \\ud835)."""
        if not s:
            return s
        try:
            s.encode("utf-8")
            return s
        except UnicodeEncodeError:
            return s.encode("utf-8", "replace").decode("utf-8")

    for sj in scraped:
        # Sanitize all string fields before insert
        sj.title = _clean_unicode(sj.title) or ""
        sj.company = _clean_unicode(sj.company) or ""
        sj.location = _clean_unicode(sj.location) or ""
        sj.description = _clean_unicode(sj.description) or ""
        if not sj.hash:
            continue
        existing = db.execute(select(Job).where(Job.hash == sj.hash)).scalar_one_or_none()
        if existing is not None:
            duplicates += 1
            continue

        try:
            scored: ScoredJobResult = score_job(db, sj, cv)
        except Exception as exc:  # noqa: BLE001
            logger.exception("scoring failed for %s: %s", sj.title, exc)
            scored = ScoredJobResult(match_score=0, rejection_reason="scoring_error")

        company_obj = _get_or_create_company(db, sj.company)

        track = detect_track(sj.title, sj.description, sj.tags)
        band = predict_salary_band(
            sj.title, sj.company, sj.description, sj.location,
            sj.salary_min, sj.salary_max, sj.currency,
        )

        job = Job(
            source=sj.source,
            source_url=sj.source_url,
            source_id=sj.source_id,
            hash=sj.hash,
            title=sj.title,
            company=sj.company,
            company_id=company_obj.id if company_obj else None,
            location=sj.location,
            remote=sj.remote,
            salary_min=sj.salary_min,
            salary_max=sj.salary_max,
            currency=sj.currency,
            posted_at=sj.posted_at,
            description=sj.description,
            tags=sj.tags,
            track=track,
            predicted_salary_band=band,
            match_score=float(scored.match_score),
            salary_in_range=scored.salary_in_range,
            remote_compatible=scored.remote_compatible,
            location_compatible=scored.location_compatible,
            rejection_reason=scored.rejection_reason,
            key_matches=scored.key_matches,
            missing_skills=scored.missing_skills,
            personalization_hooks=scored.personalization_hooks,
            status="detected",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        db.add(job)
        try:
            db.commit()
            inserted += 1
        except Exception as exc:  # noqa: BLE001
            db.rollback()
            logger.warning("insert failed for %s/%s: %s", sj.source, sj.title, exc)

    return inserted, duplicates


async def run_all_scrapers() -> list[ScrapedJob]:
    """Ejecuta los scrapers activos en paralelo y devuelve lista plana deduplicada.

    Los scrapers activos los decide `build_active_scrapers` a partir del perfil y
    sus `search_preferences`. Sin configuracion dinamica => conjunto legacy.
    """
    cv = load_cv_master()
    prefs = cv.get("search_preferences", {}) if isinstance(cv, dict) else {}
    instances = build_active_scrapers(cv, prefs)
    results = await asyncio.gather(*(s.fetch() for s in instances), return_exceptions=True)

    all_jobs: list[ScrapedJob] = []
    seen_hashes: set[str] = set()
    for res in results:
        if isinstance(res, Exception):
            logger.warning("scraper exception: %s", res)
            continue
        for j in res:
            if j.hash and j.hash in seen_hashes:
                continue
            seen_hashes.add(j.hash)
            all_jobs.append(j)

    logger.info("total scraped (post-dedup): %d", len(all_jobs))
    return all_jobs


async def scrape_and_ingest(db: Session) -> dict[str, int]:
    """Pipeline completo: scrape -> dedup -> score -> insert.

    `ingest_scraped_jobs` es síncrono y hace N llamadas a Claude para scoring,
    lo cual bloquearía el event loop si lo llamamos directo. Lo movemos a un
    thread para que el resto del backend siga respondiendo durante el scrape.
    """
    scraped = await run_all_scrapers()
    inserted, duplicates = await asyncio.to_thread(ingest_scraped_jobs, db, scraped)
    return {"scraped": len(scraped), "inserted": inserted, "duplicates": duplicates}

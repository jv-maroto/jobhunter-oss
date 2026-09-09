"""Servicios compartidos: cargar CV master, pipeline de scraping->scoring."""

from __future__ import annotations

import asyncio
import json
import logging
import threading
from datetime import datetime, timezone
from functools import lru_cache
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.models.company import Company
from app.models.job import Job
from app.schemas.job import JobOut, ScoredJobResult, ScrapedJob
from app.scoring.compatibility import constrain_score, detect_employment_type, job_compatibility
from app.scoring.qualification_assessment import assess_qualifications
from app.scoring.scorer import _heuristic_result, score_job
from app.scoring.track_detector import detect_track, predict_salary_band
from app.scrapers.country_map import resolve_regions
from app.scrapers.registry import build_active_scrapers

logger = logging.getLogger(__name__)


# ponytail: one backend process; use a DB lease if deploying multiple API workers.
_SCRAPE_LOCK = threading.Lock()
_SCRAPE_STATE: dict[str, Any] = {
    "running": False, "trigger": None, "phase": "idle",
    "started_at": None, "finished_at": None, "error": None, "skipped": None,
    "scraped": 0, "inserted": 0, "duplicates": 0,
    "filtered_geography": 0, "unconfirmed_geography": 0,
    "filtered_remote": 0, "filtered_employment": 0, "filtered_seniority": 0,
}


def scrape_runtime_state() -> dict[str, Any]:
    return dict(_SCRAPE_STATE)


@lru_cache(maxsize=1)
def load_cv_master() -> dict[str, Any]:
    """Carga cv_master.json. Cacheado en memoria."""
    path = settings.cv_master_file
    if not path.exists():
        logger.error("cv_master.json no encontrado en %s", path)
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _job_posting(job: Job) -> dict[str, Any]:
    return {field: getattr(job, field) for field in ScrapedJob.model_fields}


def current_job_metadata(job: Job, cv: dict[str, Any], *, rescore: bool = False) -> dict[str, Any]:
    posting = _job_posting(job)
    prefs = cv.get("search_preferences") or {}
    assessment = assess_qualifications(posting, cv)
    if rescore:
        result = _heuristic_result(posting, cv, assessment=assessment)
        if prefs.get("seniority") == "junior" and job.seniority_compatible is False and result.seniority_compatible is None:
            result.seniority_compatible = False
            result = constrain_score(result, posting, cv, assessment=assessment)
        result.rejection_reason = (result.rejection_reason or "").replace("(no AI evaluation)", "(current profile; no AI evaluation)", 1)
    else:
        result = constrain_score(ScoredJobResult(
            match_score=max(0, min(100, int(job.match_score or 0))),
            rejection_reason=job.rejection_reason,
            key_matches=job.key_matches or [],
            missing_skills=job.missing_skills or [],
            personalization_hooks=job.personalization_hooks or [],
            salary_in_range=job.salary_in_range,
            remote_compatible=job.remote_compatible,
            location_compatible=job.location_compatible,
            employment_compatible=job.employment_compatible,
            seniority_compatible=job.seniority_compatible if prefs.get("seniority") == "junior" else None,
        ), posting, cv, assessment=assessment)
    return {
        **result.model_dump(),
        "qualification_assessment": assessment,
        "track": detect_track(job.title, job.description, job.tags),
        "employment_type": detect_employment_type(posting),
        "predicted_salary_band": predict_salary_band(
            job.title, job.company, job.description, job.location,
            job.salary_min, job.salary_max, job.currency, job.salary_period, prefs,
        ),
    }


def discovery_job(job: Job, cv: dict[str, Any]) -> JobOut | None:
    prefs = cv.get("search_preferences") or {}
    metadata = current_job_metadata(job, cv)
    if resolve_regions(prefs) and metadata["location_compatible"] is not True:
        return None
    if prefs.get("remote_only") and metadata["remote_compatible"] is not True:
        return None
    if metadata["employment_compatible"] is False or metadata["seniority_compatible"] is False:
        return None
    target_tracks = {detect_track(str(role)) for role in prefs.get("roles") or []}
    if target_tracks and metadata["track"] not in target_tracks:
        return None
    return JobOut.model_validate(job).model_copy(update=metadata)


def refresh_job_metadata(db: Session, cv: dict[str, Any] | None = None) -> dict[str, int]:
    cv = load_cv_master() if cv is None else cv
    if not cv:
        raise ValueError("A candidate profile is required to refresh job metadata")
    jobs = db.scalars(select(Job).where(Job.status == "detected")).all()
    updated = 0
    for job in jobs:
        for field, value in current_job_metadata(job, cv, rescore=True).items():
            if field in Job.__table__.columns and getattr(job, field) != value:
                setattr(job, field, value)
        if db.is_modified(job):
            updated += 1
    db.commit()
    return {"examined": len(jobs), "updated": updated}


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


def filter_scraped_jobs(scraped: list[ScrapedJob], prefs: dict) -> tuple[list[ScrapedJob], dict[str, int]]:
    kept = []
    counts = {"filtered_geography": 0, "unconfirmed_geography": 0, "filtered_remote": 0, "filtered_employment": 0, "filtered_seniority": 0}
    for job in scraped:
        flags = job_compatibility(job.model_dump(), prefs)
        if resolve_regions(prefs) and flags["location_compatible"] is not True:
            key = "filtered_geography" if flags["location_compatible"] is False else "unconfirmed_geography"
            counts[key] += 1
        elif prefs.get("remote_only") and flags["remote_compatible"] is not True:
            counts["filtered_remote"] += 1
        elif flags["employment_compatible"] is False:
            counts["filtered_employment"] += 1
        elif flags["seniority_compatible"] is False:
            counts["filtered_seniority"] += 1
        else:
            kept.append(job)
    return kept, counts


def ingest_scraped_jobs(db: Session, scraped: list[ScrapedJob]) -> tuple[int, int]:
    """Inserta ofertas nuevas (dedup por hash). Devuelve (insertados, duplicados)."""
    inserted = 0
    duplicates = 0
    cv = load_cv_master()
    prefs = cv.get("search_preferences") or {}

    def _clean_unicode(s: str | None) -> str | None:
        """Strip lone surrogate halves that SQLite refuses to encode (e.g. \\ud835)."""
        if not s:
            return s
        try:
            s.encode("utf-8")
            return s
        except UnicodeEncodeError:
            return s.encode("utf-8", "replace").decode("utf-8")

    cap = int(getattr(settings, "max_scored_jobs_per_run", 0) or 0)
    scored_count = 0
    skipped_scoring = 0

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
            if existing.status == "detected":
                changed = False
                salary_fields = ("salary_min", "salary_max", "currency", "salary_period")
                amounts = ("salary_min", "salary_max")
                salary_consistent = all(
                    getattr(existing, field) is None or getattr(sj, field) is None
                    or getattr(existing, field) == getattr(sj, field)
                    for field in salary_fields
                )
                units_confirmed = (
                    all(getattr(existing, field) is None or getattr(existing, field) == getattr(sj, field) for field in amounts)
                    or (existing.currency is not None and existing.salary_period is not None
                        and existing.currency == sj.currency and existing.salary_period == sj.salary_period)
                )
                fields = ["description", "employment_type"]
                if salary_consistent and units_confirmed:
                    fields.extend(salary_fields)
                for field in fields:
                    old_value, new_value = getattr(existing, field), getattr(sj, field)
                    missing = old_value is None or (isinstance(old_value, str) and not old_value.strip())
                    supplied = new_value is not None and (not isinstance(new_value, str) or bool(new_value.strip()))
                    if missing and supplied:
                        setattr(existing, field, new_value)
                        changed = True
                if changed:
                    for field, value in current_job_metadata(existing, cv, rescore=True).items():
                        if field in Job.__table__.columns and (field != "employment_type" or existing.employment_type is None):
                            setattr(existing, field, value)
                    try:
                        db.commit()
                    except Exception as exc:
                        db.rollback()
                        logger.warning("duplicate enrichment failed for %s/%s: %s", sj.source, sj.title, exc)
            continue

        if not filter_scraped_jobs([sj], prefs)[0]:
            continue

        if cap and scored_count >= cap:
            scored = _heuristic_result(sj.model_dump(), cv)
            skipped_scoring += 1
        else:
            try:
                scored = score_job(db, sj, cv)
                scored_count += 1
            except Exception as exc:  # noqa: BLE001
                logger.exception("scoring failed for %s: %s", sj.title, exc)
                scored = ScoredJobResult(match_score=0, rejection_reason="scoring_error")

        scored = constrain_score(scored, sj.model_dump(), cv)
        company_obj = _get_or_create_company(db, sj.company)

        track = detect_track(sj.title, sj.description, sj.tags)
        band = predict_salary_band(
            sj.title, sj.company, sj.description, sj.location,
            sj.salary_min, sj.salary_max, sj.currency, sj.salary_period, prefs,
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
            salary_period=sj.salary_period,
            employment_type=detect_employment_type(sj.model_dump()),
            posted_at=sj.posted_at,
            description=sj.description,
            tags=sj.tags,
            track=track,
            predicted_salary_band=band,
            match_score=float(scored.match_score),
            salary_in_range=scored.salary_in_range,
            remote_compatible=scored.remote_compatible,
            location_compatible=scored.location_compatible,
            employment_compatible=scored.employment_compatible,
            seniority_compatible=scored.seniority_compatible,
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

    if skipped_scoring:
        logger.warning(
            "AI scoring cap reached (%d/run): %d jobs received labeled heuristic estimates.",
            cap,
            skipped_scoring,
        )

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
    ok_count = 0
    fail_count = 0
    for scraper, res in zip(instances, results, strict=False):
        name = scraper.__class__.__name__
        if isinstance(res, Exception):
            # Log with full traceback so operators can debug: silently swallowing
            # scraper failures used to hide 200+ missing jobs behind a "0 new"
            # message on the frontend.
            logger.exception("scraper %s failed: %s", name, res)
            fail_count += 1
            continue
        ok_count += 1
        for j in res:
            if j.hash and j.hash in seen_hashes:
                continue
            seen_hashes.add(j.hash)
            all_jobs.append(j)

    logger.info(
        "scrapers: %d ok, %d failed. Total scraped (post-dedup): %d",
        ok_count, fail_count, len(all_jobs),
    )
    return all_jobs


async def _scrape_and_ingest(db: Session) -> dict[str, int | str]:
    """Pipeline completo: scrape -> dedup -> score -> insert.

    `ingest_scraped_jobs` es síncrono y hace N llamadas a Claude para scoring,
    lo cual bloquearía el event loop si lo llamamos directo. Lo movemos a un
    thread para que el resto del backend siga respondiendo durante el scrape.
    """
    from app.onboarding.detect import is_onboarded

    if not is_onboarded():
        # Sin perfil no hay regiones ni queries reales: scrapear con la plantilla
        # llenaba la DB de ofertas de cualquier pais antes del onboarding.
        logger.warning("scrape omitido: completa el onboarding antes de buscar ofertas")
        return {"scraped": 0, "inserted": 0, "duplicates": 0, "skipped": "not_onboarded"}

    _SCRAPE_STATE["phase"] = "scraping"
    scraped = await run_all_scrapers()
    scraped_count = len(scraped)
    _SCRAPE_STATE["scraped"] = scraped_count
    cv = load_cv_master()
    eligible, filtered = filter_scraped_jobs(scraped, cv.get("search_preferences") or {})
    eligible_hashes = {job.hash for job in eligible}
    existing_hashes = set(db.scalars(select(Job.hash).where(Job.status == "detected")).all())
    existing_to_enrich = [job for job in scraped if job.hash in existing_hashes and job.hash not in eligible_hashes]
    scraped = eligible

    # Scraping IA (opcional): re-rankea las ofertas nuevas por relevancia antes de
    # ingerir. Solo si el usuario lo activo y hay IA disponible. Con fallback total.
    if getattr(settings, "ai_scraping_enabled", False):
        try:
            from app.ai.router import ai_available

            if ai_available():
                from app.scrapers.rerank import rerank_jobs

                cv = load_cv_master()
                scraped = await asyncio.to_thread(rerank_jobs, scraped, cv, 40)
        except Exception as exc:  # noqa: BLE001
            logger.warning("rerank IA fallo, sigo sin reordenar: %s", exc)

    _SCRAPE_STATE["phase"] = "scoring"
    inserted, duplicates = await asyncio.to_thread(ingest_scraped_jobs, db, scraped + existing_to_enrich)
    return {"scraped": scraped_count, "inserted": inserted, "duplicates": duplicates, **filtered}


async def scrape_and_ingest(db: Session, *, trigger: str = "manual") -> dict[str, Any]:
    if not _SCRAPE_LOCK.acquire(blocking=False):
        return {"status": "already_running", **scrape_runtime_state()}
    _SCRAPE_STATE.update({
        "running": True, "trigger": trigger, "phase": "starting",
        "started_at": datetime.now(timezone.utc).isoformat(), "finished_at": None, "error": None, "skipped": None,
        **{key: 0 for key in ("scraped", "inserted", "duplicates", "filtered_geography", "unconfirmed_geography", "filtered_remote", "filtered_employment", "filtered_seniority")},
    })
    task = asyncio.create_task(_scrape_and_ingest(db))
    cancelled = False
    try:
        while not task.done():
            try:
                await asyncio.shield(task)
            except asyncio.CancelledError:
                cancelled = True
        result = task.result()
        _SCRAPE_STATE.update(result)
        _SCRAPE_STATE["phase"] = "finished"
        if cancelled:
            raise asyncio.CancelledError
        return result
    except asyncio.CancelledError:
        if _SCRAPE_STATE["phase"] != "finished":
            _SCRAPE_STATE.update({"phase": "cancelled", "error": "Scrape task cancelled"})
        raise
    except Exception as exc:
        _SCRAPE_STATE.update({"phase": "failed", "error": str(exc)[:200]})
        raise
    finally:
        _SCRAPE_STATE.update({"running": False, "finished_at": datetime.now(timezone.utc).isoformat()})
        _SCRAPE_LOCK.release()

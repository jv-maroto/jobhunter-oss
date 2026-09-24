"""One-click broad discovery without changing the candidate's preferences."""
from __future__ import annotations

import asyncio
import logging
import re
import threading
import unicodedata
from copy import deepcopy
from datetime import datetime, timezone

from sqlalchemy import select

from app.db import SessionLocal
from app.models.career_analysis import CareerAnalysis
from app.models.company_board import CompanyBoard
from app.schemas.job import ScrapedJob
from app.scrapers.base import compute_job_hash
from app.scrapers.country_map import COUNTRY_MAP
from app.scrapers.jobspy_scraper import JobspyPlan, JobspyScraper
from app.services import ingest_scraped_jobs, load_cv_master
from app.task_history import begin_task, recover_latest, update_task

logger = logging.getLogger(__name__)
_LOCK = threading.Lock()
_STATE = {"running": False, "phase": "idle", "scraped": 0, "inserted": 0, "duplicates": 0,
          "completed_sources": 0, "total_sources": 0, "error": None}


def now():
    return datetime.now(timezone.utc).isoformat()


def discovery_status():
    return deepcopy(_STATE)


def restore_discovery():
    latest = recover_latest("discovery")
    if latest:
        _STATE.update(latest)


def reserve_discovery():
    if not _LOCK.acquire(blocking=False):
        return False
    try:
        previous_rotation = int(_STATE.get("rotation", -1))
        _STATE.clear()
        _STATE.update(running=True, phase="starting", started_at=now(), finished_at=None,
                      scraped=0, inserted=0, duplicates=0, completed_sources=0, total_sources=0,
                      error=None, source_errors=[], rotation=previous_rotation + 1)
        _STATE["task_id"] = begin_task("discovery", _STATE)
        return True
    except BaseException:
        _STATE.update(running=False, phase="failed", error="No se pudo guardar la búsqueda")
        _LOCK.release()
        raise


def persist():
    update_task(_STATE["task_id"], _STATE)


def discovery_roles(cv: dict, db) -> list[str]:
    latest = db.scalar(select(CareerAnalysis).where(CareerAnalysis.status == "completed")
                       .order_by(CareerAnalysis.id.desc()).limit(1))
    roles = [role.get("title") for role in (latest.result or {}).get("roles", [])
             if isinstance(role, dict) and role.get("fit") != "exploratory"] if latest else []
    if not roles:
        roles = (cv.get("search_preferences") or {}).get("roles") or []
    if not roles:
        for entry in cv.get("experience") or []:
            if isinstance(entry, dict):
                roles.append(entry.get("role") or entry.get("title") or entry.get("role_en"))
    return list(dict.fromkeys(role.strip()[:120] for role in roles if isinstance(role, str) and role.strip()))[:25]


def relevant(job: ScrapedJob, roles: list[str], cv: dict) -> bool:
    text = (job.title + " " + job.description).lower()
    words = {word for role in roles for word in re.findall(r"[\w+#.]+", role.lower())
             if len(word) > 2 and word not in {"senior", "junior", "remote", "remoto", "the", "and", "con", "para"}}
    skills = cv.get("skills") or {}
    if isinstance(skills, dict):
        words.update(str(skill).lower() for group in skills.values() if isinstance(group, list) for skill in group)
    return any(re.search(r"(?<!\w)" + re.escape(word) + r"(?!\w)", text) for word in words if word)


def discovery_search_terms(roles: list[str]) -> list[str]:
    """Short international query labels; original evidence-based roles stay intact."""
    rules = (
        (r"\bdevops\b", "DevOps engineer"),
        (r"\b(?:ciberseguridad|cybersecurity|cyber security)\b", "cyber security analyst"),
        (r"\b(?:sysadmin|administrador(?:a)? de sistemas|administracion de sistemas|systems? administrator)\b", "systems administrator"),
        (r"\b(?:redes?|network(?:ing)?|networks)\b", "network administrator"),
        (r"\b(?:full[ -]?stack)\b", "full stack developer"),
        (r"\b(?:php|prestashop)\b", "PHP developer"),
        (r"\b(?:soporte|support|helpdesk|help desk)\b", "IT support"),
        (r"\b(?:ia|ai|inteligencia artificial|artificial intelligence)\b", "AI engineer"),
        (r"\b(?:desktop|escritorio)\b", "Python developer"),
        (r"\b(?:automatizacion|automation|herramientas internas|internal tools)\b", "automation developer"),
        (r"\b(?:python|fastapi)\b", "Python developer"),
    )
    terms, seen = [], set()
    for role in roles:
        normalized = "".join(char for char in unicodedata.normalize("NFKD", role.casefold())
                             if not unicodedata.combining(char))
        query = next((term for pattern, term in rules if re.search(pattern, normalized)),
                     " ".join(role.split())[:120])
        if query and query.casefold() not in seen:
            seen.add(query.casefold())
            terms.append(query)
    return terms


async def fetch_country(code: str, role: str):
    params = COUNTRY_MAP[code]
    plan = JobspyPlan(sites=["indeed"], queries=[role], location=params["location"],
                      country_indeed=params["indeed"], results_wanted=20, hours_old=168)
    return await JobspyScraper([plan]).fetch()


async def fetch_registered_board(board: dict):
    from app.company_boards.readers import fetch_board
    result = await fetch_board(board["provider"], board["slug"], board["name"])
    jobs = []
    for row in result["jobs"]:
        jobs.append(ScrapedJob(source=board["provider"], source_url=row["url"],
                              title=row["title"], company=row["company"], location=row.get("location") or "",
                              remote=row.get("remote") is True, description=row["description"],
                              salary_min=row.get("salary_min"), salary_max=row.get("salary_max"),
                              currency=row.get("currency"), salary_period=row.get("salary_period"),
                              tags=["global-discovery", "eligibility-unverified"],
                              hash=compute_job_hash(row["title"], row["company"], row.get("location") or "")))
    return jobs


def ingest_partial(jobs, cv, budget):
    with SessionLocal() as db:
        return ingest_scraped_jobs(db, jobs, cv_override=cv, globally_discovered=True, ai_budget=budget)


async def run_discovery():
    tasks = []
    try:
        cv = load_cv_master()
        with SessionLocal() as db:
            roles = discovery_roles(cv, db)
            boards = [{"name": row.name, "provider": row.provider, "slug": row.slug}
                      for row in db.scalars(select(CompanyBoard).where(CompanyBoard.status == "active")
                                            .order_by(CompanyBoard.id).limit(8))]
        if not roles:
            raise ValueError("Añade tu CV o una profesión al perfil para orientar la búsqueda")
        rotation = _STATE["rotation"]
        queries = discovery_search_terms(roles)
        relevance_roles = roles + queries
        countries = list(COUNTRY_MAP)
        _STATE.update(phase="searching", queries=queries, roles=roles, countries=countries,
                      total_sources=len(countries) + len(boards),
                      coverage_note="Se consultan países con conectores configurados y empresas ATS registradas. No se garantiza cobertura mundial; ubicación desconocida se conserva.")
        persist()
        semaphore = asyncio.Semaphore(4)
        async def fetch_one(label, function, *args):
            async with semaphore:
                try:
                    async with asyncio.timeout(90):
                        from app.job_availability import verify_scraped_jobs

                        fetched = await function(*args)
                        relevant_jobs = [job for job in fetched if relevant(job, relevance_roles, cv)]
                        checked = await verify_scraped_jobs(relevant_jobs, max_checks=8, ats_present=function is fetch_registered_board)
                        for job, result in checked:
                            job.availability = result
                        return label, [job for job, result in checked], None
                except Exception as exc:
                    return label, [], type(exc).__name__
        for board in boards:
            tasks.append(asyncio.create_task(fetch_one(board["name"], fetch_registered_board, board)))
        for index, code in enumerate(countries):
            tasks.append(asyncio.create_task(fetch_one(code, fetch_country, code, queries[(rotation + index) % len(queries)])))
        # Discovery stays fast; deep AI evaluation is explicit on each offer.
        budget = {"remaining": 0}
        seen = set()
        for future in asyncio.as_completed(tasks):
            label, jobs, error = await future
            _STATE["scraped"] += len(jobs)
            if error:
                _STATE["source_errors"].append({"source": label, "error": error})
            fresh = []
            for job in jobs:
                if not job.hash:
                    job.hash = compute_job_hash(job.title, job.company, job.location)
                if job.hash not in seen and relevant(job, relevance_roles, cv):
                    seen.add(job.hash)
                    fresh.append(job)
            # Keep the DB session owned by its worker until ingestion completes.
            work = asyncio.create_task(asyncio.to_thread(ingest_partial, fresh, cv, budget))
            try:
                inserted, duplicates = await asyncio.shield(work)
            except asyncio.CancelledError:
                await work
                raise
            except Exception as exc:
                logger.exception("Discovery ingestion failed for source %s", label)
                _STATE["source_errors"].append({"source": label, "error": type(exc).__name__})
                inserted, duplicates = 0, 0
            _STATE["inserted"] += inserted
            _STATE["duplicates"] += duplicates
            _STATE["completed_sources"] += 1
            _STATE["last_source"] = label
            persist()
        _STATE.update(phase="finished", connector_health="partially_unverified")
        if _STATE["source_errors"]:
            _STATE["error"] = f"{len(_STATE['source_errors'])} fuentes no se pudieron completar; se conservan las demás ofertas."
    except asyncio.CancelledError:
        _STATE.update(phase="interrupted", error="Búsqueda interrumpida; los resultados ya guardados se conservan")
        raise
    except Exception as exc:
        logger.exception("Discovery failed")
        _STATE.update(phase="failed", error=str(exc) if isinstance(exc, ValueError) else "La búsqueda falló; se conservan los resultados guardados")
    finally:
        for task in tasks:
            if not task.done():
                task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        _STATE.update(running=False, finished_at=now())
        try:
            persist()
        finally:
            _LOCK.release()

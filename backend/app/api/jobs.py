"""Endpoints de jobs."""

from __future__ import annotations

import asyncio
import logging
import re
import unicodedata
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from app.ai.cover_letter import generate_cover_letter
from app.ai.cv_generator import _detect_language, generate_cv
from app.config import settings
from app.db import get_db
from app.models.application import Application
from app.models.job import Job
from app.schemas.job import (
    JobOut,
    JobPatch,
    JobsListOut,
    PrepareApplicationOut,
)
from app.services import load_cv_master, scrape_and_ingest

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/jobs", tags=["jobs"])


def _company_slug(name: str | None, job_id: int) -> str:
    """Slug filesystem-safe: lowercase, sin acentos, separado por '-'.
    Fallback al job_id si el nombre queda vacío."""
    if name:
        s = unicodedata.normalize("NFD", name)
        s = "".join(c for c in s if unicodedata.category(c) != "Mn")
        s = re.sub(r"[^a-zA-Z0-9]+", "-", s).strip("-").lower()
        s = s[:60].rstrip("-")
        if s:
            return s
    return str(job_id)


@router.get("", response_model=JobsListOut)
def list_jobs(
    status: str | None = Query(default=None),
    min_score: float | None = Query(default=None, ge=0, le=100),
    source: str | None = Query(default=None),
    track: str | None = Query(default=None, description="dev | sysadmin"),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> JobsListOut:
    stmt = select(Job).order_by(desc(Job.match_score), desc(Job.created_at))
    if status:
        stmt = stmt.where(Job.status == status)
    if min_score is not None:
        stmt = stmt.where(Job.match_score >= min_score)
    if source:
        stmt = stmt.where(Job.source == source)
    if track:
        stmt = stmt.where(Job.track == track)

    total = db.execute(
        select(func.count()).select_from(stmt.order_by(None).subquery())
    ).scalar() or 0
    items = db.execute(stmt.offset(offset).limit(limit)).scalars().all()
    return JobsListOut(total=int(total), items=[JobOut.model_validate(j) for j in items])


@router.get("/swipe", response_model=list[JobOut])
def swipe_jobs(
    track: str = Query(default="dev", description="dev | sysadmin"),
    remote_only: bool = Query(default=False),
    min_band: str | None = Query(default=None, description="high | mid → filter por banda mínima"),
    limit: int = Query(default=40, ge=1, le=100),
    db: Session = Depends(get_db),
) -> list[JobOut]:
    """Cola de ofertas pendientes de decidir, ordenada por mejor sueldo primero."""
    band_rank = {"high": 4, "mid": 3, "unknown": 2, "low": 1}
    min_rank = band_rank.get(min_band or "", 0)

    stmt = (
        select(Job)
        .where(Job.track == track)
        .where(Job.status == "detected")
    )
    if remote_only:
        stmt = stmt.where(Job.remote.is_(True))

    items = db.execute(stmt).scalars().all()
    if min_rank:
        items = [j for j in items if band_rank.get(j.predicted_salary_band, 0) >= min_rank]

    # Sort: explicit salary first (desc), then by band, then by match_score
    def sort_key(j: Job):
        sal = j.salary_max or j.salary_min or 0
        rank = band_rank.get(j.predicted_salary_band, 0)
        return (-sal, -rank, -j.match_score)

    items.sort(key=sort_key)
    return [JobOut.model_validate(j) for j in items[:limit]]


# ---------------------------------------------------------------------------
# Scrape (background task + status polling) — declared BEFORE /{job_id}
# so the literal paths take precedence over the int catch-all.
# ---------------------------------------------------------------------------

_SCRAPE_STATE: dict[str, object] = {
    "running": False,
    "started_at": None,
    "finished_at": None,
    "scraped": 0,
    "inserted": 0,
    "duplicates": 0,
    "error": None,
}


async def _run_scrape_background() -> None:
    from app.db import SessionLocal
    _SCRAPE_STATE["running"] = True
    _SCRAPE_STATE["started_at"] = datetime.utcnow().isoformat()
    _SCRAPE_STATE["finished_at"] = None
    _SCRAPE_STATE["error"] = None
    db = SessionLocal()
    try:
        result = await scrape_and_ingest(db)
        _SCRAPE_STATE["scraped"] = result.get("scraped", 0)
        _SCRAPE_STATE["inserted"] = result.get("inserted", 0)
        _SCRAPE_STATE["duplicates"] = result.get("duplicates", 0)
    except Exception as exc:  # noqa: BLE001
        _SCRAPE_STATE["error"] = str(exc)[:200]
        logger.exception("scrape background failed: %s", exc)
    finally:
        db.close()
        _SCRAPE_STATE["running"] = False
        _SCRAPE_STATE["finished_at"] = datetime.utcnow().isoformat()


@router.post("/scrape-now", tags=["jobs"])
async def scrape_now(background_tasks: BackgroundTasks) -> dict:
    from app.onboarding.detect import is_onboarded

    if not is_onboarded():
        raise HTTPException(
            status_code=409,
            detail="Completa el onboarding antes de buscar ofertas (sin perfil no hay queries).",
        )
    if _SCRAPE_STATE.get("running"):
        return {"status": "already_running", **_SCRAPE_STATE}
    background_tasks.add_task(_run_scrape_background)
    return {"status": "started"}


@router.get("/scrape-status", tags=["jobs"])
def scrape_status() -> dict:
    return dict(_SCRAPE_STATE)


@router.get("/{job_id}", response_model=JobOut)
def get_job(job_id: int, db: Session = Depends(get_db)) -> JobOut:
    job = db.get(Job, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return JobOut.model_validate(job)


@router.patch("/{job_id}", response_model=JobOut)
def patch_job(job_id: int, patch: JobPatch, db: Session = Depends(get_db)) -> JobOut:
    job = db.get(Job, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if patch.status:
        job.status = patch.status
        if patch.status == "applied" and not job.applied_at:
            job.applied_at = datetime.utcnow()
    if patch.notes is not None:
        job.notes = patch.notes
    if patch.applied_at is not None:
        job.applied_at = patch.applied_at
    db.commit()
    db.refresh(job)
    return JobOut.model_validate(job)


@router.post("/{job_id}/prepare-application", response_model=PrepareApplicationOut)
async def prepare_application(job_id: int, db: Session = Depends(get_db)) -> PrepareApplicationOut:
    job = db.get(Job, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    cv_master = load_cv_master()
    if not cv_master:
        raise HTTPException(status_code=500, detail="cv_master.json no disponible")

    out_dir = settings.data_path / "applications" / _company_slug(job.company, job.id)
    out_dir.mkdir(parents=True, exist_ok=True)

    job_dict = {
        "id": job.id,
        "title": job.title,
        "company": job.company,
        "location": job.location,
        "description": job.description,
    }
    hooks = list(job.personalization_hooks or [])

    # Detect language synchronously (cheap) so CV + cover can run in parallel
    lang = _detect_language(job.description or job.title or "")

    cv_task = asyncio.to_thread(generate_cv, cv_master, job_dict, out_dir, lang)
    cover_task = asyncio.to_thread(
        generate_cover_letter, cv_master, job_dict, hooks, out_dir, lang
    )
    (pdf_cv, typst_src, lang), (pdf_cover, cover_content) = await asyncio.gather(
        cv_task, cover_task
    )

    # Copy PDFs to a human-friendly export folder (~/.../cvs-out/) so the user
    # can grab them with a readable name for email/upload. Local personal setup.
    try:
        import shutil, re
        from datetime import date as _d
        cvs_out = Path.home() / "Documentos" / "Proyectos" / "jobhunter" / "cvs-out"
        cvs_out.mkdir(parents=True, exist_ok=True)
        safe_company = re.sub(r"[^A-Za-z0-9]+", "_", (job.company or "unknown")).strip("_")
        stamp = _d.today().isoformat()
        prefix = f"{safe_company}_{stamp}_job{job.id}"
        if pdf_cv and Path(pdf_cv).exists():
            shutil.copy2(pdf_cv, cvs_out / f"{prefix}_cv.pdf")
        if pdf_cover and Path(pdf_cover).exists():
            shutil.copy2(pdf_cover, cvs_out / f"{prefix}_cover.pdf")
    except Exception as _e:
        logger.warning("cvs-out export failed for job %s: %s", job.id, _e)

    job.cv_path = str(pdf_cv)
    job.cover_letter_path = str(pdf_cover)
    if job.status == "detected":
        job.status = "prepared"

    app_row = Application(
        job_id=job.id,
        cv_path=str(pdf_cv),
        cover_letter_path=str(pdf_cover),
        cv_content=typst_src,
        cover_letter_content=cover_content,
        language=lang,
        status="prepared",
    )
    db.add(app_row)
    db.commit()
    db.refresh(job)

    return PrepareApplicationOut(
        job_id=job.id,
        cv_path=str(pdf_cv),
        cover_letter_path=str(pdf_cover),
        cv_content=typst_src,
        cover_letter_content=cover_content,
        language=lang,
    )


@router.get("/{job_id}/cv")
def get_cv(job_id: int, db: Session = Depends(get_db)):
    """Serve the generated CV PDF inline so the browser can preview it."""
    job = db.get(Job, job_id)
    if not job or not job.cv_path:
        raise HTTPException(status_code=404, detail="CV not generated for this job")
    path = Path(job.cv_path)
    if not path.exists():
        raise HTTPException(status_code=410, detail=f"CV file missing on disk: {path}")
    safe_name = f"cv_{_company_slug(job.company, job.id)}.pdf"
    return FileResponse(
        path,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{safe_name}"'},
    )


@router.get("/{job_id}/cover")
def get_cover_letter(job_id: int, db: Session = Depends(get_db)):
    """Serve the generated cover letter PDF inline."""
    job = db.get(Job, job_id)
    if not job or not job.cover_letter_path:
        raise HTTPException(status_code=404, detail="Cover letter not generated for this job")
    path = Path(job.cover_letter_path)
    if not path.exists():
        raise HTTPException(status_code=410, detail=f"Cover file missing on disk: {path}")
    safe_name = f"cover_{_company_slug(job.company, job.id)}.pdf"
    return FileResponse(
        path,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{safe_name}"'},
    )


# Scrape routes have been moved above /{job_id} to avoid path conflict.

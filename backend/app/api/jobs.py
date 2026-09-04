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


@router.delete("/{job_id}")
def delete_job(job_id: int, db: Session = Depends(get_db)) -> dict:
    """Delete a job + all its applications + PDF files on disk.

    Removes cascade-safe:
      - Application rows for this job
      - The application folder in data/applications/{slug}/
      - The corresponding cvs-out subfolders (best-effort — filenames encode
        job id, so we glob for any that end in `_job{id}` under any date dir).
    Does NOT touch the DB row for other tables that might reference this job.
    """
    from app.models.application import Application

    job = db.get(Job, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    company = job.company or "unknown"
    app_rows = db.execute(
        select(Application).where(Application.job_id == job_id)
    ).scalars().all()

    # Delete DB rows first (transactional)
    for a in app_rows:
        db.delete(a)
    db.delete(job)
    db.commit()

    # Best-effort file cleanup — never fails the request
    try:
        slug = _company_slug(company, job_id)
        app_dir = settings.data_path / "applications" / slug
        if app_dir.exists():
            import shutil
            shutil.rmtree(app_dir, ignore_errors=True)
    except Exception as e:  # noqa: BLE001
        logger.warning("Failed to remove application folder for job %s: %s", job_id, e)

    try:
        # cvs-out/YYYY-MM-DD/{key}_{HH-MM-SS}_{Company}_job{id}/
        # Only when the user has configured CVS_OUT_DIR in .env.
        cvs_out = settings.cvs_out_path
        if cvs_out is not None and cvs_out.exists():
            import shutil
            for day_dir in cvs_out.iterdir():
                if not day_dir.is_dir():
                    continue
                for sub in day_dir.iterdir():
                    if sub.is_dir() and sub.name.endswith(f"_job{job_id}"):
                        shutil.rmtree(sub, ignore_errors=True)
    except Exception as e:  # noqa: BLE001
        logger.warning("Failed to remove cvs-out folders for job %s: %s", job_id, e)

    return {"deleted": True, "job_id": job_id, "applications": len(app_rows)}


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
    # gather with return_exceptions so a typst failure in either half surfaces
    # as an HTTP 500 with the real message, instead of persisting an orphan
    # cv_path/cover_letter_path pointing at a file that was never written.
    from app.ai.cv_generator import CVGenerationError
    results = await asyncio.gather(cv_task, cover_task, return_exceptions=True)
    cv_result, cover_result = results
    if isinstance(cv_result, CVGenerationError):
        raise HTTPException(status_code=500, detail=f"CV generation failed: {cv_result}")
    if isinstance(cv_result, Exception):
        raise HTTPException(status_code=500, detail=f"CV generation crashed: {cv_result}")
    if isinstance(cover_result, CVGenerationError):
        raise HTTPException(status_code=500, detail=f"Cover letter generation failed: {cover_result}")
    if isinstance(cover_result, Exception):
        raise HTTPException(status_code=500, detail=f"Cover letter generation crashed: {cover_result}")
    (pdf_cv, typst_src, lang) = cv_result
    (pdf_cover, cover_content) = cover_result

    # Defence-in-depth: both PDFs must exist on disk before we touch the DB.
    if not (pdf_cv and Path(pdf_cv).exists()):
        raise HTTPException(status_code=500, detail=f"CV PDF missing after generation: expected {pdf_cv}")
    if not (pdf_cover and Path(pdf_cover).exists()):
        raise HTTPException(status_code=500, detail=f"Cover PDF missing after generation: expected {pdf_cover}")

    # Optional: export to a human-friendly folder tree so the user can grab
    # everything per application with a readable name for email/upload.
    # Enabled by setting CVS_OUT_DIR in .env (absolute path).
    #
    # Structure inside CVS_OUT_DIR:
    #   YYYY-MM-DD/
    #     {desc_key}_{HH-MM-SS}_{Company}_job{id}/
    #       cv.pdf
    #       cover.pdf
    #       message.txt  (cover body as plain text — paste into email)
    #
    # desc_key = 86400 - seconds_since_midnight (padded 5 digits) so a plain
    # alphabetical sort in Finder shows the newest of the day first.
    cvs_out_root = settings.cvs_out_path
    if cvs_out_root is not None:
        try:
            import re
            import shutil
            from datetime import datetime as _dt
            now = _dt.now()
            secs_of_day = now.hour * 3600 + now.minute * 60 + now.second
            desc_key = f"{86400 - secs_of_day:05d}"
            hhmmss = now.strftime("%H-%M-%S")
            # Unicode-aware slug: keep ñÑ, accents, letters, digits and hyphens.
            safe_company = re.sub(
                r"[^\w-]+", "_", (job.company or "unknown"), flags=re.UNICODE
            ).strip("_")
            app_dir = (
                cvs_out_root
                / now.date().isoformat()
                / f"{desc_key}_{hhmmss}_{safe_company}_job{job.id}"
            )
            app_dir.mkdir(parents=True, exist_ok=True)
            if pdf_cv and Path(pdf_cv).exists():
                shutil.copy2(pdf_cv, app_dir / "cv.pdf")
            if pdf_cover and Path(pdf_cover).exists():
                shutil.copy2(pdf_cover, app_dir / "cover.pdf")
            # Plain-text version of the cover for quick paste into email/DM
            if cover_content:
                (app_dir / "message.txt").write_text(cover_content, encoding="utf-8")
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


def _resolve_pdf_path(
    saved_path: str | None, job: Job, kind: str, db: Session
) -> Path | None:
    """Resolve a PDF path robustly across environment changes.

    Handles the common breakage of an absolute path stored in the DB that no
    longer exists because the user moved between local runs and Docker (paths
    like `/app/data/...` vs `/Users/.../backend/data/...`) or renamed folders.

    Resolution order:
      1. If `saved_path` exists as-is → return it.
      2. If it's absolute, try re-basing it into the current `settings.data_path`
         by matching the tail after `/data/`.
      3. Try the canonical fallback: `settings.data_path/applications/{slug}/{kind}.pdf`.
      4. Give up → None.

    If a fallback works, persist the corrected path so the next call is a
    direct hit (self-healing).
    """
    if saved_path:
        p = Path(saved_path)
        if p.exists():
            return p

    def _persist(new_path: Path) -> Path:
        setattr(job, "cv_path" if kind == "cv" else "cover_letter_path", str(new_path))
        try:
            db.commit()
        except Exception:  # noqa: BLE001
            db.rollback()
        return new_path

    # Try re-basing an old absolute path into the new data dir
    if saved_path:
        raw = saved_path.replace("\\", "/")
        marker = "/data/"
        if marker in raw:
            tail = raw.split(marker, 1)[1]  # e.g. "applications/coforge/cv.pdf"
            candidate = settings.data_path / tail
            if candidate.exists():
                return _persist(candidate)

    # Canonical fallback: data/applications/{slug}/{kind}.pdf
    slug = _company_slug(job.company, job.id)
    canonical = settings.data_path / "applications" / slug / f"{kind}.pdf"
    if canonical.exists():
        return _persist(canonical)

    return None


@router.get("/{job_id}/cv")
def get_cv(job_id: int, db: Session = Depends(get_db)):
    """Serve the generated CV PDF inline so the browser can preview it."""
    job = db.get(Job, job_id)
    if not job or not job.cv_path:
        raise HTTPException(status_code=404, detail="CV not generated for this job")
    path = _resolve_pdf_path(job.cv_path, job, "cv", db)
    if path is None:
        raise HTTPException(
            status_code=410,
            detail=(
                f"CV file missing on disk (checked '{job.cv_path}' and "
                f"'{settings.data_path}/applications/{_company_slug(job.company, job.id)}/cv.pdf'). "
                "Regenerate with 'Prepare application'."
            ),
        )
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
    path = _resolve_pdf_path(job.cover_letter_path, job, "cover", db)
    if path is None:
        raise HTTPException(
            status_code=410,
            detail=(
                f"Cover file missing on disk (checked '{job.cover_letter_path}' and "
                f"'{settings.data_path}/applications/{_company_slug(job.company, job.id)}/cover.pdf'). "
                "Regenerate with 'Prepare application'."
            ),
        )
    safe_name = f"cover_{_company_slug(job.company, job.id)}.pdf"
    return FileResponse(
        path,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{safe_name}"'},
    )


# Scrape routes have been moved above /{job_id} to avoid path conflict.

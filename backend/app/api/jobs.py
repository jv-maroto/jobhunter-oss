"""Endpoints de jobs."""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import re
import unicodedata
from pathlib import Path
from typing import Literal
from uuid import uuid4

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request
from fastapi.responses import FileResponse
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.ai.cover_letter import generate_cover_letter
from app.ai.cv_generator import _detect_language, generate_cv
from app.apply.state import TERMINAL_STATUSES, UNSET, transition_job
from app.config import settings
from app.db import get_db
from app.models.application import Application
from app.models.job import Job
from app.rate_limit import limiter
from app.schemas.job import (
    JobImport,
    JobImportOut,
    JobOut,
    JobPatch,
    JobsListOut,
    JobTrack,
    PrepareApplicationOut,
    canonical_job_url,
)
from app.services import (
    current_job_metadata,
    discovery_job,
    load_cv_master,
    scrape_and_ingest,
    scrape_runtime_state,
)

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


def _company_folder_name(
    name: str | None, job_id: int, db: Session | None = None
) -> str:
    """Folder name for `data/applications/<here>/`.

    Delegates the actual naming to the user-configurable scheme stored in
    AppSetting (see /settings/cv-storage). Falls back to the default
    "company-id" scheme if no DB session is available (e.g. one-off scripts).
    """
    from datetime import date as _d

    slug = _company_slug(name, job_id)
    if db is None:
        # No DB → use the safe default without hitting AppSetting
        return f"{slug}-{job_id}" if slug != str(job_id) else f"job-{job_id}"

    from app import app_settings as _svc
    scheme = _svc.cv_naming_scheme(db)
    return _svc.build_folder_name(scheme, slug, job_id, _d.today().isoformat())


def _applications_root(db: Session | None) -> Path:
    """Resolves the base folder where per-application directories live.

    Uses the user-configured runtime setting if present, otherwise the
    default `data/applications` from settings.data_path.
    """
    fallback = (settings.data_path / "applications").resolve()
    if db is None:
        return fallback
    from app import app_settings as _svc
    return _svc.cv_root_dir(db, fallback=fallback)


@router.get("", response_model=JobsListOut)
def list_jobs(
    status: str | None = Query(default=None),
    min_score: float | None = Query(default=None, ge=0, le=100),
    source: str | None = Query(default=None),
    track: JobTrack | Literal["all", ""] | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> JobsListOut:
    stmt = select(Job).order_by(desc(Job.created_at))
    if status:
        stmt = stmt.where(Job.status == status)
    if source:
        stmt = stmt.where(Job.source == source)
    cv = load_cv_master()
    # ponytail: local-sized job collection; move metadata predicates into indexed columns if this grows large.
    items = []
    for job in db.scalars(stmt):
        if job.source == "manual" or job.saved_by_user:
            item = JobOut.model_validate(job).model_copy(update=current_job_metadata(job, cv, rescore=True))
        elif job.status != "detected":
            item = JobOut.model_validate(job)
        else:
            item = discovery_job(job, cv)
        if item is None or (track and track != "all" and item.track != track):
            continue
        if min_score is not None and item.match_score < min_score:
            continue
        items.append(item)
    items.sort(key=lambda item: item.match_score, reverse=True)
    return JobsListOut(total=len(items), items=items[offset:offset + limit])



@router.get("/swipe", response_model=list[JobOut])
def swipe_jobs(
    track: JobTrack | Literal["all", ""] | None = Query(default=None),
    remote_only: bool = Query(default=False),
    min_band: str | None = Query(default=None, description="high | mid → filter por banda mínima"),
    limit: int = Query(default=40, ge=1, le=100),
    db: Session = Depends(get_db),
) -> list[JobOut]:
    band_rank = {"high": 4, "mid": 3, "unknown": 2, "low": 1}
    min_rank = band_rank.get(min_band or "", 0)
    stmt = select(Job).where(Job.status == "detected").order_by(desc(Job.created_at))
    if remote_only:
        stmt = stmt.where(Job.remote.is_(True))
    cv = load_cv_master()
    items = []
    for job in db.scalars(stmt):
        item = discovery_job(job, cv)
        if item is None or item.match_score < 30:
            continue
        if track and track != "all" and item.track != track:
            continue
        if min_rank and band_rank.get(item.predicted_salary_band, 0) < min_rank:
            continue
        items.append(item)
    items.sort(key=lambda item: (-item.match_score, -band_rank.get(item.predicted_salary_band, 0)))
    return items[:limit]



# ---------------------------------------------------------------------------
# Scrape (background task + status polling) — declared BEFORE /{job_id}
# so the literal paths take precedence over the int catch-all.
# ---------------------------------------------------------------------------

async def _run_scrape_background() -> None:
    from app.db import SessionLocal

    db = SessionLocal()
    try:
        await scrape_and_ingest(db)
    except Exception as exc:
        logger.exception("scrape background failed: %s", exc)
    finally:
        db.close()


@router.post("/scrape-now", tags=["jobs"])
@limiter.limit("6/minute")
async def scrape_now(request: Request, background_tasks: BackgroundTasks) -> dict:
    from app.onboarding.detect import is_onboarded

    if not is_onboarded():
        raise HTTPException(
            status_code=409,
            detail="Completa el onboarding antes de buscar ofertas (sin perfil no hay queries).",
        )
    state = scrape_runtime_state()
    if state["running"]:
        return {"status": "already_running", **state}
    background_tasks.add_task(_run_scrape_background)
    return {"status": "started"}


@router.get("/scrape-status", tags=["jobs"])
def scrape_status() -> dict:
    return scrape_runtime_state()


@router.post("/import", response_model=JobImportOut)
def import_job(payload: JobImport, db: Session = Depends(get_db)) -> JobImportOut:
    def normalized_content(title: str, company: str, location: str, description: str) -> str:
        return json.dumps([" ".join((value or "").split()).casefold()
                           for value in (title, company, location, description)], ensure_ascii=False)

    content = normalized_content(payload.title, payload.company, payload.location, payload.description)
    identity = payload.url or content
    digest = hashlib.sha256(identity.encode("utf-8")).hexdigest()
    existing_id = None
    for row in db.execute(select(Job.id, Job.source_url, Job.hash, Job.title, Job.company,
                                 Job.location, Job.description)):
        if row.hash == digest or normalized_content(row.title, row.company, row.location, row.description) == content:
            existing_id = row.id
            break
        if payload.url and row.source_url:
            try:
                if canonical_job_url(row.source_url) == payload.url:
                    existing_id = row.id
                    break
            except (ValueError, UnicodeError):
                continue
    cv = load_cv_master()
    if existing_id is not None:
        job = db.get(Job, existing_id)
        job.saved_by_user = True
        if not job.source_url and payload.url:
            job.source_url = payload.url
        if not (job.description or "").strip():
            job.description = payload.description
        db.commit()
        db.refresh(job)
        return JobImportOut(job=JobOut.model_validate(job).model_copy(
            update=current_job_metadata(job, cv, rescore=True)), created=False)

    job = Job(source="manual", source_url=payload.url or "", hash=digest,
              title=payload.title, company=payload.company, description=payload.description,
              location=payload.location, remote=payload.remote, saved_by_user=True)
    db.add(job)
    db.flush()
    metadata = current_job_metadata(job, cv, rescore=True)
    for field, value in metadata.items():
        if field in Job.__table__.columns:
            setattr(job, field, value)
    db.commit()
    db.refresh(job)
    return JobImportOut(job=JobOut.model_validate(job).model_copy(update=metadata), created=True)


@router.get("/{job_id}", response_model=JobOut)
def get_job(job_id: int, db: Session = Depends(get_db)) -> JobOut:
    job = db.get(Job, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    result = JobOut.model_validate(job)
    metadata = current_job_metadata(job, load_cv_master(), rescore=job.source == "manual" or job.saved_by_user)
    return result.model_copy(update=metadata)


@router.patch("/{job_id}", response_model=JobOut)
def patch_job(job_id: int, patch: JobPatch, db: Session = Depends(get_db)) -> JobOut:
    job = db.get(Job, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    fields = patch.model_fields_set
    next_action = patch.next_action if "next_action" in fields else job.next_action
    next_action = next_action.strip() or None if next_action else None
    next_action_at = patch.next_action_at if "next_action_at" in fields else job.next_action_at
    if "next_action" in fields and next_action is None:
        next_action_at = None
    if (patch.status or job.status) in TERMINAL_STATUSES:
        next_action = next_action_at = None
    if next_action_at is not None and not next_action:
        raise HTTPException(status_code=422, detail="A follow-up date requires a next action")
    if patch.status or "applied_at" in fields:
        try:
            transition_job(db, job, patch.status or job.status,
                           application_id=patch.application_id,
                           applied_at=patch.applied_at if "applied_at" in fields else UNSET)
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
    if "notes" in fields:
        job.notes = patch.notes
    job.next_action = next_action
    job.next_action_at = next_action_at
    db.commit()
    db.refresh(job)
    return JobOut.model_validate(job)


@router.delete("/{job_id}")
def delete_job(job_id: int, db: Session = Depends(get_db)) -> dict:
    """Delete a job + all its applications + PDF files on disk.

    Removes cascade-safe:
      - Application rows for this job
      - The application folder in data/applications/job-{id}/
      - The corresponding cvs-out subfolders (best-effort — filenames encode
        job id, so we glob for any that end in `_job{id}` under any date dir).
    Does NOT touch the DB row for other tables that might reference this job.
    """
    from app.models.application import Application

    job = db.get(Job, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    app_rows = db.execute(
        select(Application).where(Application.job_id == job_id)
    ).scalars().all()

    # Delete DB rows first (transactional)
    for a in app_rows:
        db.delete(a)
    db.delete(job)
    db.commit()

    # Best-effort file cleanup — never fails the request. Try the current
    # naming scheme + a few legacy fallbacks so old data is cleaned too.
    try:
        import shutil
        root = _applications_root(db)
        candidates = [
            root / _company_folder_name(job.company, job_id, db=db),
            root / f"job-{job_id}",
            root / str(job_id),
        ]
        for app_dir in candidates:
            if app_dir.exists():
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
@limiter.limit("20/minute")
async def prepare_application(
    request: Request, job_id: int, db: Session = Depends(get_db)
) -> PrepareApplicationOut:
    job = db.get(Job, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    cv_master = load_cv_master()
    if not cv_master:
        raise HTTPException(status_code=500, detail="cv_master.json no disponible")
    preparation_track = current_job_metadata(job, cv_master)["track"]

    # Folder named by the user-configured scheme (see /settings/cv-storage).
    # Job id is included by default to prevent collisions when several
    # roles come from the same employer.
    out_dir = (
        _applications_root(db)
        / _company_folder_name(job.company, job.id, db=db)
        / uuid4().hex
    )
    out_dir.mkdir(parents=True, exist_ok=True)

    job_dict = {
        "id": job.id,
        "title": job.title,
        "company": job.company,
        "location": job.location,
        "description": job.description,
        "track": preparation_track,
        "salary_min": job.salary_min,
        "salary_max": job.salary_max,
        "currency": job.currency,
        "salary_period": job.salary_period,
        "remote": job.remote,
        "employment_type": job.employment_type,
    }
    hooks = list(job.personalization_hooks or [])

    lang = _detect_language(job.description or job.title or "")
    from app.ai.cv_generator import CVGenerationError

    stage = "CV"
    try:
        pdf_cv, typst_src, lang = await asyncio.to_thread(generate_cv, cv_master, job_dict, out_dir, lang)
        stage = "Cover letter"
        pdf_cover, cover_content = await asyncio.to_thread(
            generate_cover_letter, cv_master, job_dict, hooks, out_dir, lang
        )
    except CVGenerationError as exc:
        raise HTTPException(status_code=500, detail=f"{stage} generation failed: {exc}") from exc
    except Exception as exc:
        logger.exception("%s generation crashed for job %s", stage, job_id)
        raise HTTPException(status_code=500, detail=f"{stage} generation crashed. Check backend logs for details.") from exc

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

    documents = cv_master.get("application_documents") or {}
    documents = documents if isinstance(documents, dict) else {}
    mappings = documents.get("cv_by_track") or {}
    entry = mappings.get(preparation_track, {}) if isinstance(mappings, dict) else {}
    entry = entry if isinstance(entry, dict) else {}
    app_row = Application(
        job_id=job.id,
        cv_path=str(pdf_cv),
        cover_letter_path=str(pdf_cover),
        cv_content=typst_src,
        cover_letter_content=cover_content,
        language=lang,
        status="prepared",
        cv_source_filename=entry.get("filename") if documents.get("mode") == "existing" else None,
        cv_sha256=hashlib.sha256(Path(pdf_cv).read_bytes()).hexdigest(),
        cv_mode="existing" if documents.get("mode") == "existing" else "generated",
    )
    db.add(app_row)
    db.commit()
    db.refresh(job)

    return PrepareApplicationOut(
        application_id=app_row.id,
        job_id=job.id,
        cv_path=str(pdf_cv),
        cover_letter_path=str(pdf_cover),
        cv_content=typst_src,
        cover_letter_content=cover_content,
        language=lang,
        cv_provenance={"mode": app_row.cv_mode, "source_filename": app_row.cv_source_filename,
                       "sha256": app_row.cv_sha256, "language": lang},
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
      3. Give up → None; never substitute another application from the same company.

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
                "The CV file is no longer available. Prepare the application again."
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
                "The cover letter is no longer available. Prepare the application again."
            ),
        )
    safe_name = f"cover_{_company_slug(job.company, job.id)}.pdf"
    return FileResponse(
        path,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{safe_name}"'},
    )


# Scrape routes have been moved above /{job_id} to avoid path conflict.

from __future__ import annotations

import logging
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel, ConfigDict, StringConstraints, field_serializer
from sqlalchemy import case, func, or_, select
from sqlalchemy.orm import Session

from app.ai.cover_letter import _compile_cover_pdf
from app.ai.cv_generator import CVGenerationError
from app.config import settings
from app.db import get_db
from app.models.application import Application
from app.models.job import Job
from app.schemas.job import JobOut
from app.services import current_job_metadata, load_cv_master

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/applications", tags=["applications"])


class ApplicationOut(BaseModel):
    application_id: int | None
    job: JobOut
    status: str
    provider: str | None
    prepared_at: datetime | None
    submitted_at: datetime | None
    language: str | None
    cv_url: str | None
    cover_url: str | None
    cv_source_filename: str | None
    cv_sha256: str | None
    cv_mode: str | None
    cover_letter_content: str | None

    @field_serializer("prepared_at", "submitted_at", when_used="json")
    def serialize_utc(self, value: datetime | None) -> str | None:
        if value is None:
            return None
        return (value if value.tzinfo else value.replace(tzinfo=timezone.utc)).isoformat()


class ApplicationsListOut(BaseModel):
    total: int
    items: list[ApplicationOut]


class CoverLetterPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    cover_letter_content: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=20000)
    ]


def _review(job: Job, application: Application | None, profile: dict) -> ApplicationOut:
    # Older copies recorded their provenance in cv_content before dedicated columns existed.
    source = re.match(
        r"^Existing CV '(.+)' copied unchanged for role '",
        application.cv_content or "",
    ) if application else None
    digest = re.search(
        r"SHA-256: ([0-9a-fA-F]{64})\.", application.cv_content or ""
    ) if source else None
    job_out = JobOut.model_validate(job)
    if profile:
        job_out.qualification_assessment = current_job_metadata(job, profile).get(
            "qualification_assessment", job_out.qualification_assessment
        )
    return ApplicationOut(
        application_id=application.id if application else None,
        job=job_out,
        status=application.status if application else job.status,
        provider=application.provider if application else None,
        prepared_at=application.created_at if application else None,
        submitted_at=application.submitted_at if application else job.applied_at,
        language=application.language if application else None,
        cv_url=f"/applications/{application.id}/cv" if application and application.cv_path else None,
        cover_url=f"/applications/{application.id}/cover"
        if application and application.cover_letter_path else None,
        cv_source_filename=(application.cv_source_filename or (source[1] if source else None))
        if application else None,
        cv_sha256=(application.cv_sha256 or (digest[1].lower() if digest else None))
        if application else None,
        cv_mode=(application.cv_mode or ("existing" if source else None))
        if application else None,
        cover_letter_content=application.cover_letter_content if application else None,
    )


@router.get("", response_model=ApplicationsListOut)
def list_applications(
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    due_before: datetime | None = Query(default=None),
    db: Session = Depends(get_db),
) -> ApplicationsListOut:
    latest_id = (
        select(Application.id)
        .where(Application.job_id == Job.id)
        .order_by(Application.created_at.desc(), Application.id.desc())
        .limit(1)
        .correlate(Job)
        .scalar_subquery()
    )
    stmt = select(Job, Application).outerjoin(Application, Application.id == latest_id).where(
        or_(
            Application.id.is_not(None),
            Job.status != "detected",
            Job.cv_path.is_not(None),
            Job.cover_letter_path.is_not(None),
            Job.next_action_at.is_not(None),
            Job.saved_by_user.is_(True),
        )
    )
    if due_before is not None:
        if due_before.tzinfo is not None:
            due_before = due_before.astimezone(timezone.utc).replace(tzinfo=None)
        stmt = stmt.where(
            Job.next_action_at <= due_before,
            Job.status.not_in(("offer", "rejected", "ghosted")),
        )
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    activity = func.coalesce(
        Application.submitted_at, Application.created_at, Job.applied_at, Job.created_at
    )
    activity = case((Job.updated_at > activity, Job.updated_at), else_=activity)
    order = Job.next_action_at.asc() if due_before is not None else activity.desc()
    rows = db.execute(stmt.order_by(order, Job.id.desc()).limit(limit).offset(offset))
    profile = load_cv_master()
    return ApplicationsListOut(total=total, items=[_review(job, app, profile) for job, app in rows])


def _get_application(application_id: int, db: Session) -> Application:
    application = db.get(Application, application_id)
    if application is None or application.job is None:
        raise HTTPException(status_code=404, detail="Application not found")
    return application


@router.get("/{application_id}", response_model=ApplicationOut)
def get_application(application_id: int, db: Session = Depends(get_db)) -> ApplicationOut:
    application = _get_application(application_id, db)
    return _review(application.job, application, load_cv_master())


@router.get("/{application_id}/versions", response_model=list[ApplicationOut])
def list_application_versions(
    application_id: int, db: Session = Depends(get_db)
) -> list[ApplicationOut]:
    application = _get_application(application_id, db)
    versions = db.scalars(select(Application).where(
        Application.job_id == application.job_id,
    ).order_by(Application.created_at.desc(), Application.id.desc()).limit(100))
    profile = load_cv_master()
    return [_review(application.job, version, profile) for version in versions]


def _document_path(saved_path: str | None) -> Path:
    if not saved_path:
        raise HTTPException(status_code=404, detail="Document not generated for this application")
    root = (settings.data_path / "applications").resolve()
    candidates = [Path(saved_path)]
    raw = saved_path.replace("\\", "/")
    if "/data/" in raw:
        candidates.append(settings.data_path / raw.split("/data/", 1)[1])
    for candidate in candidates:
        try:
            resolved = candidate.resolve()
            if resolved.is_relative_to(root) and resolved.is_file():
                return resolved
        except (OSError, RuntimeError, ValueError):
            continue
    raise HTTPException(status_code=410, detail="The saved application document is unavailable")


@router.get("/{application_id}/cv")
def get_application_cv(application_id: int, db: Session = Depends(get_db)) -> FileResponse:
    application = _get_application(application_id, db)
    return FileResponse(
        _document_path(application.cv_path),
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="cv_application_{application.id}.pdf"'},
    )


@router.get("/{application_id}/cover")
def get_application_cover(application_id: int, db: Session = Depends(get_db)) -> FileResponse:
    application = _get_application(application_id, db)
    return FileResponse(
        _document_path(application.cover_letter_path),
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="cover_application_{application.id}.pdf"'},
    )


@router.patch("/{application_id}/cover", response_model=ApplicationOut)
def patch_application_cover(
    application_id: int, patch: CoverLetterPatch, db: Session = Depends(get_db)
) -> ApplicationOut:
    application = _get_application(application_id, db)
    if application.status not in {"prepared", "draft"} or application.submitted_at is not None:
        raise HTTPException(
            status_code=409,
            detail="Submitted application documents are read-only. Prepare a new version to edit the cover letter.",
        )
    profile = load_cv_master()
    if not profile:
        raise HTTPException(status_code=409, detail="A profile is required to render the cover letter")
    out_dir = settings.data_path / "applications" / f"job-{application.job_id}" / uuid4().hex
    out_dir.mkdir(parents=True, exist_ok=False)
    pdf_path = out_dir / "cover.pdf"
    try:
        _compile_cover_pdf(
            patch.cover_letter_content,
            profile,
            {"company": application.job.company},
            out_dir,
            pdf_path,
            application.language,
        )
        (out_dir / "cover.txt").write_text(patch.cover_letter_content, encoding="utf-8")
        if not pdf_path.is_file():
            raise CVGenerationError("Cover letter PDF missing after rendering")
        previous_path = application.cover_letter_path
        application.cover_letter_path = str(pdf_path)
        application.cover_letter_content = patch.cover_letter_content
        latest_id = db.scalar(
            select(Application.id)
            .where(Application.job_id == application.job_id)
            .order_by(Application.created_at.desc(), Application.id.desc())
            .limit(1)
        )
        if latest_id == application.id and application.job.cover_letter_path == previous_path:
            application.job.cover_letter_path = str(pdf_path)
        db.commit()
    except Exception as exc:
        db.rollback()
        shutil.rmtree(out_dir, ignore_errors=True)
        logger.exception("Cover letter revision failed for application %s", application_id)
        raise HTTPException(status_code=500, detail="Cover letter could not be saved; previous version retained") from exc
    db.refresh(application)
    return _review(application.job, application, profile)

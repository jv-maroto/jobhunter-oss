"""Endpoints de aplicar (Pilar 3). El dashboard dispara la aplicacion."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.apply.orchestrator import apply_to_job
from app.db import get_db
from app.models.application import Application
from app.models.apply_queue import ApplyQueueItem
from app.models.job import Job

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/jobs", tags=["apply"])


class ApplyIn(BaseModel):
    provider: str | None = None  # "extension" | "manual" | "playwright" | None=auto
    language: str | None = None


@router.post("/{job_id}/apply")
def apply_endpoint(job_id: int, body: ApplyIn, db: Session = Depends(get_db)) -> dict:
    job = db.get(Job, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job no encontrado")
    try:
        result = apply_to_job(db, job, provider_override=body.provider, language=body.language)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return result.as_dict()


@router.get("/{job_id}/apply/status")
def apply_status(job_id: int, db: Session = Depends(get_db)) -> dict:
    job = db.get(Job, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job no encontrado")
    item = db.execute(
        select(ApplyQueueItem)
        .where(ApplyQueueItem.job_id == job_id)
        .order_by(desc(ApplyQueueItem.id))
    ).scalars().first()
    app_row = db.execute(
        select(Application).where(Application.job_id == job_id).order_by(desc(Application.id))
    ).scalars().first()
    return {
        "job_id": job_id,
        "job_status": job.status,
        "queue": {"id": item.id, "status": item.status, "platform": item.platform} if item else None,
        "application": {
            "id": app_row.id,
            "status": app_row.status,
            "provider": app_row.provider,
            "submitted_at": app_row.submitted_at.isoformat() if app_row.submitted_at else None,
        }
        if app_row
        else None,
    }

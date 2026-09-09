from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.application import Application
from app.models.job import Job

UNSET = object()
TERMINAL_STATUSES = {"offer", "rejected", "ghosted"}


def transition_job(
    db: Session,
    job: Job,
    status: str,
    *,
    application_id: int | None = None,
    applied_at: datetime | None | object = UNSET,
    provider: str = "manual",
) -> Application | None:
    app = db.get(Application, application_id) if application_id is not None else None
    if application_id is not None and (app is None or app.job_id != job.id):
        raise ValueError("Application does not belong to this job")
    if app is None:
        query = select(Application).where(Application.job_id == job.id)
        if status in {"interviewing", "offer", "rejected", "ghosted"}:
            app = db.scalar(query.where(Application.submitted_at.is_not(None)).order_by(Application.id.desc()))
        app = app or db.scalar(query.order_by(Application.id.desc()))

    if status == "prepared":
        if app is None or app.submitted_at is not None or app.status not in {"prepared", "draft"}:
            previous = app
            app = Application(
                job_id=job.id,
                status="prepared",
                language=previous.language if previous else "en",
                cv_path=previous.cv_path if previous else job.cv_path,
                cover_letter_path=previous.cover_letter_path if previous else job.cover_letter_path,
                cv_content=previous.cv_content if previous else None,
                cover_letter_content=previous.cover_letter_content if previous else None,
                cv_source_filename=previous.cv_source_filename if previous else None,
                cv_sha256=previous.cv_sha256 if previous else None,
                cv_mode=previous.cv_mode if previous else None,
            )
            db.add(app)
        job.applied_at = None
    elif status == "detected":
        job.applied_at = None
    else:
        if app is None:
            app = Application(job_id=job.id, language="en", cv_path=job.cv_path,
                              cover_letter_path=job.cover_letter_path)
            db.add(app)
        app.status = "submitted" if status == "applied" else status
        app.provider = app.provider or provider
        app.apply_url = app.apply_url or job.source_url or None
        if applied_at is not UNSET:
            date = applied_at
        else:
            date = app.submitted_at or job.applied_at
            if date is None and status == "applied" and provider == "manual":
                date = datetime.utcnow()
        app.submitted_at = date
        job.applied_at = date

    job.status = status
    if status in TERMINAL_STATUSES:
        job.next_action = None
        job.next_action_at = None
    return app

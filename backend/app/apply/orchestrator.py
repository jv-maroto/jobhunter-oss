"""Orquestador de aplicar: elige provider por plataforma y prepara la accion.

extension -> encola un ApplyQueueItem que la extension consume y rellena (el
usuario revisa y pulsa Enviar). manual -> registra Application y devuelve la URL.
mcp/playwright(off) -> caen a manual (los MCP no envian; Playwright es opt-in).
"""

from __future__ import annotations

import logging

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.apply.base import ApplyMaterials, ApplyMode, ApplyResult, ApplyStatus
from app.apply.platforms import host_to_platform
from app.config import settings
from app.models.application import Application
from app.models.apply_queue import ApplyQueueItem
from app.models.job import Job

logger = logging.getLogger(__name__)


def _latest_application(db: Session, job_id: int) -> Application | None:
    return db.execute(
        select(Application).where(Application.job_id == job_id).order_by(desc(Application.id))
    ).scalars().first()


def _materials(app: Application | None, language: str | None) -> ApplyMaterials:
    if app is None:
        return ApplyMaterials(language=language or "en")
    return ApplyMaterials(
        cv_path=app.cv_path,
        cover_letter_path=app.cover_letter_path,
        language=language or app.language or "en",
    )


def apply_to_job(
    db: Session, job: Job, provider_override: str | None = None, language: str | None = None
) -> ApplyResult:
    platform, default_mode = host_to_platform(job.source_url)

    mode = ApplyMode(provider_override) if provider_override else default_mode
    # Los MCP no envian solicitudes; Playwright solo si esta habilitado.
    if mode == ApplyMode.mcp:
        mode = ApplyMode.manual
    if mode == ApplyMode.playwright and not settings.apply_playwright_enabled:
        mode = ApplyMode.manual

    app = _latest_application(db, job.id)
    materials = _materials(app, language)

    if mode in (ApplyMode.extension, ApplyMode.playwright):
        item = ApplyQueueItem(
            job_id=job.id,
            application_id=app.id if app else None,
            platform=platform,
            apply_url=job.source_url,
            status="queued",
            materials=materials.as_dict(),
        )
        db.add(item)
        db.commit()
        db.refresh(item)
        msg = (
            "En cola para la extension (revisa y pulsa Enviar)"
            if mode == ApplyMode.extension
            else "En cola para Playwright (auto-envio)"
        )
        return ApplyResult(
            mode=mode,
            status=ApplyStatus.queued,
            job_id=job.id,
            platform=platform,
            application_id=app.id if app else None,
            queue_id=item.id,
            apply_url=job.source_url,
            message=msg,
        )

    # manual
    if app is None:
        app = Application(
            job_id=job.id,
            status="prepared",
            provider="manual",
            apply_url=job.source_url,
            language=materials.language,
        )
        db.add(app)
    else:
        app.provider = "manual"
        app.apply_url = job.source_url
    db.commit()
    db.refresh(app)
    return ApplyResult(
        mode=ApplyMode.manual,
        status=ApplyStatus.needs_manual,
        job_id=job.id,
        platform=platform,
        application_id=app.id,
        apply_url=job.source_url,
        message="Abre la oferta y aplica a mano (esta plataforma no se automatiza).",
    )


def record_applied(
    db: Session,
    job: Job,
    platform: str,
    apply_url: str,
    screening_answers: dict | None = None,
    queue_id: int | None = None,
) -> Application:
    """Registra que una oferta se envio (desde la extension) y avanza el pipeline."""
    from datetime import datetime

    app = _latest_application(db, job.id)
    if app is None:
        app = Application(job_id=job.id, language="en")
        db.add(app)
    app.status = "submitted"
    app.provider = "extension"
    app.apply_url = apply_url or app.apply_url
    app.submitted_at = datetime.utcnow()
    if screening_answers:
        app.screening_answers = screening_answers

    # Avanza el pipeline (forward-only basico).
    if job.status in ("detected", "prepared", "interested"):
        job.status = "applied"
        job.applied_at = datetime.utcnow()

    if queue_id is not None:
        item = db.get(ApplyQueueItem, queue_id)
        if item is not None:
            item.status = "submitted"

    db.commit()
    db.refresh(app)
    return app

"""Matching correo->oferta y actualizacion reversible del pipeline.

Reglas (forward-only salvo 'rejected', que es alcanzable desde cualquier estado
no terminal). Guardarrailes: solo auto-aplica con confianza alta; nunca borra;
guarda previous_job_status para poder Deshacer; idempotente por gmail_id.
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.integrations.gmail.base import EmailMessage
from app.integrations.gmail.query import normalize_company
from app.models.email_event import EmailEvent
from app.models.job import Job

logger = logging.getLogger(__name__)

# Orden forward-only de los estados "de avance".
_ORDER = {"detected": 0, "prepared": 1, "applied": 2, "interviewing": 3, "offer": 4}
_TERMINAL = {"rejected", "ghosted"}

TYPE_TO_STATUS = {
    "rechazo": "rejected",
    "invitacion_entrevista": "interviewing",
    "oferta": "offer",
    "acuse_recibo": "applied",
}
_AUTO_TYPES = {"rechazo", "invitacion_entrevista", "oferta"}


def _apply_status(job: Job, new_status: str) -> tuple[bool, str]:
    """Aplica el cambio respetando forward-only. Devuelve (cambiado, estado_previo)."""
    prev = job.status
    if prev in _TERMINAL:
        return False, prev
    if new_status == "rejected":
        job.status = "rejected"
        return True, prev
    if _ORDER.get(new_status, -1) > _ORDER.get(prev, -1):
        job.status = new_status
        return True, prev
    return False, prev


def match_job(db: Session, classified: dict[str, Any], msg: EmailMessage) -> tuple[Job | None, str, float]:
    """Empareja el correo con una oferta por nombre de empresa. (job, metodo, conf)."""
    target = normalize_company(classified.get("company") or msg.from_name or "")
    if len(target) < 3:
        return None, "none", 0.0

    jobs = db.execute(select(Job)).scalars().all()
    best: Job | None = None
    for job in jobs:
        jc = normalize_company(job.company)
        if not jc or len(jc) < 3:
            continue
        if target == jc or target in jc or jc in target:
            # Prefiere la oferta no terminal mas reciente.
            if best is None or (job.status not in _TERMINAL and (job.created_at or 0) > (best.created_at or 0)):
                best = job

    if best is None:
        return None, "none", 0.0
    return best, "company", float(classified.get("confidence", 0.0))


def process_email(db: Session, msg: EmailMessage, classified: dict[str, Any], account: str) -> EmailEvent | None:
    """Procesa un correo ya clasificado: matchea, aplica reglas y persiste EmailEvent.

    Idempotente: si ya existe un EmailEvent con ese gmail_id, no hace nada.
    """
    existing = db.execute(
        select(EmailEvent).where(EmailEvent.gmail_id == msg.gmail_id)
    ).scalar_one_or_none()
    if existing is not None:
        return existing

    etype = classified.get("type", "irrelevante")
    job, method, conf = match_job(db, classified, msg)

    status = "no_change"
    applied_change: str | None = None
    prev_status: str | None = None
    auto_th = settings.gmail_auto_apply_threshold
    match_th = settings.gmail_match_threshold

    if etype == "irrelevante":
        status = "no_change"
    elif job is None or conf < match_th:
        # Relevante pero sin match fiable -> a revision manual.
        status = "pending_review"
    elif etype in _AUTO_TYPES and conf >= auto_th:
        new_status = TYPE_TO_STATUS[etype]
        changed, prev_status = _apply_status(job, new_status)
        if changed:
            applied_change = f"{prev_status}->{job.status}"
            status = "auto_applied"
            note = f"[gmail] {etype}: {classified.get('summary_es', '')}".strip()
            job.notes = (job.notes + "\n" if job.notes else "") + note
        else:
            status = "no_change"
    elif etype == "acuse_recibo":
        changed, prev_status = _apply_status(job, "applied")
        if changed:
            applied_change = f"{prev_status}->{job.status}"
            status = "applied"
        else:
            status = "no_change"
    elif etype == "peticion_info":
        note = f"[gmail] piden info: {classified.get('next_action_es', '')}".strip()
        job.notes = (job.notes + "\n" if job.notes else "") + note
        status = "pending_review"
    else:
        status = "pending_review"

    event = EmailEvent(
        gmail_id=msg.gmail_id,
        thread_id=msg.thread_id,
        account=account,
        job_id=job.id if job else None,
        type=etype,
        company=classified.get("company") or (job.company if job else None),
        from_email=msg.from_email,
        from_name=msg.from_name,
        subject=(msg.subject or "")[:500],
        snippet=(msg.snippet or "")[:512],
        received_at=msg.received_at,
        match_method=method,
        match_confidence=conf,
        classified_json=classified,
        status=status,
        applied_status_change=applied_change,
        previous_job_status=prev_status,
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    return event


def undo_event(db: Session, event: EmailEvent) -> bool:
    """Revierte el cambio de estado que provoco un EmailEvent (si lo hubo)."""
    if not event.job_id or not event.previous_job_status:
        return False
    job = db.get(Job, event.job_id)
    if job is None:
        return False
    job.status = event.previous_job_status
    event.status = "dismissed"
    event.applied_status_change = None
    db.commit()
    return True

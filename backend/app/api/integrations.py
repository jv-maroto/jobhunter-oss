"""Endpoints de integraciones (Gmail tracking, Pilar 4). Local-first, sin auth."""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_db
from app.integrations.gmail import store
from app.integrations.gmail.clients import get_client
from app.integrations.gmail.pipeline import TYPE_TO_STATUS, _apply_status, undo_event
from app.models.email_event import EmailEvent
from app.models.job import Job

logger = logging.getLogger(__name__)
router = APIRouter(tags=["integrations"])


# ---------------- Gmail connect / status ----------------

class GmailConnectBody(BaseModel):
    mode: str  # "api" | "imap"
    scope: str | None = None
    email: str | None = None
    app_password: str | None = None
    client_secret: Any | None = None  # contenido del client_secret.json (modo api)


def _status_payload() -> dict[str, Any]:
    state = store.load_state()
    return {
        "enabled": settings.enable_gmail_tracking,
        "mode": state.get("mode"),
        "account": state.get("account", ""),
        "connected": bool(state.get("mode")),
        "scope": state.get("scope", settings.gmail_scope),
        "last_sync_at": state.get("last_sync_at"),
    }


@router.get("/integrations/gmail/status")
def gmail_status() -> dict[str, Any]:
    return _status_payload()


@router.post("/integrations/gmail/connect")
def gmail_connect(body: GmailConnectBody) -> dict[str, Any]:
    now = datetime.utcnow().isoformat()

    if body.mode == "imap":
        if not (body.email and body.app_password):
            raise HTTPException(status_code=400, detail="email y app_password requeridos")
        store.write_secure(
            store.IMAP_FILE,
            json.dumps({"email": body.email, "app_password": body.app_password}),
        )
        from app.integrations.gmail.imap_client import ImapGmailClient

        err = ImapGmailClient().check_connection()
        if err is not None:
            store.disconnect()
            raise HTTPException(status_code=400, detail=err)
        store.update_state(mode="imap", account=body.email, connected_at=now)
        return _status_payload()

    if body.mode == "api":
        if body.client_secret:
            content = (
                body.client_secret
                if isinstance(body.client_secret, str)
                else json.dumps(body.client_secret)
            )
            store.write_secure(store.CLIENT_SECRET_FILE, content)
        try:
            from app.integrations.gmail.api_client import run_oauth_flow

            result = run_oauth_flow()
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(status_code=400, detail=f"OAuth fallo: {exc}") from exc
        store.update_state(
            mode="api", account=result.get("account", ""), scope=settings.gmail_scope, connected_at=now
        )
        return _status_payload()

    raise HTTPException(status_code=400, detail="mode debe ser 'api' o 'imap'")


@router.post("/integrations/gmail/disconnect")
def gmail_disconnect() -> dict[str, Any]:
    store.disconnect()
    return {"ok": True}


@router.post("/integrations/gmail/sync")
async def gmail_sync(db: Session = Depends(get_db)) -> dict[str, Any]:
    from app.integrations.gmail.sync import run_sync

    if get_client() is None:
        raise HTTPException(status_code=400, detail="Gmail no esta conectado")
    return await asyncio.to_thread(run_sync, db)


# ---------------- Email events ----------------

@router.get("/email-events")
def list_events(
    status: str | None = None,
    type: str | None = None,
    job_id: int | None = None,
    include_irrelevant: bool = False,
    limit: int = 100,
    db: Session = Depends(get_db),
) -> list[dict[str, Any]]:
    stmt = select(EmailEvent).order_by(desc(EmailEvent.received_at), desc(EmailEvent.id))
    if status:
        stmt = stmt.where(EmailEvent.status == status)
    if type:
        stmt = stmt.where(EmailEvent.type == type)
    if job_id is not None:
        stmt = stmt.where(EmailEvent.job_id == job_id)
    if not include_irrelevant:
        stmt = stmt.where(EmailEvent.type != "irrelevante")
    rows = db.execute(stmt.limit(limit)).scalars().all()
    return [_event_dict(e) for e in rows]


def _event_dict(e: EmailEvent) -> dict[str, Any]:
    return {
        "id": e.id,
        "type": e.type,
        "company": e.company,
        "from_name": e.from_name,
        "from_email": e.from_email,
        "subject": e.subject,
        "snippet": e.snippet,
        "received_at": e.received_at.isoformat() if e.received_at else None,
        "job_id": e.job_id,
        "status": e.status,
        "match_method": e.match_method,
        "match_confidence": e.match_confidence,
        "applied_status_change": e.applied_status_change,
        "summary_es": (e.classified_json or {}).get("summary_es", ""),
        "next_action_es": (e.classified_json or {}).get("next_action_es", ""),
    }


def _get_event(db: Session, event_id: int) -> EmailEvent:
    ev = db.get(EmailEvent, event_id)
    if ev is None:
        raise HTTPException(status_code=404, detail="EmailEvent no encontrado")
    return ev


@router.post("/email-events/{event_id}/apply")
def apply_event(event_id: int, db: Session = Depends(get_db)) -> dict[str, Any]:
    """Aplica manualmente el cambio de estado sugerido (para pending_review)."""
    ev = _get_event(db, event_id)
    if not ev.job_id:
        raise HTTPException(status_code=400, detail="El evento no esta vinculado a una oferta")
    new_status = TYPE_TO_STATUS.get(ev.type)
    if not new_status:
        raise HTTPException(status_code=400, detail="Este tipo de correo no cambia el estado")
    job = db.get(Job, ev.job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Oferta no encontrada")
    changed, prev = _apply_status(job, new_status)
    ev.status = "applied"
    ev.applied_status_change = f"{prev}->{job.status}" if changed else None
    ev.previous_job_status = prev
    db.commit()
    return _event_dict(ev)


@router.post("/email-events/{event_id}/dismiss")
def dismiss_event(event_id: int, db: Session = Depends(get_db)) -> dict[str, Any]:
    ev = _get_event(db, event_id)
    ev.status = "dismissed"
    db.commit()
    return _event_dict(ev)


class RelinkBody(BaseModel):
    job_id: int


@router.post("/email-events/{event_id}/relink")
def relink_event(event_id: int, body: RelinkBody, db: Session = Depends(get_db)) -> dict[str, Any]:
    ev = _get_event(db, event_id)
    if db.get(Job, body.job_id) is None:
        raise HTTPException(status_code=404, detail="Oferta no encontrada")
    ev.job_id = body.job_id
    ev.match_method = "manual"
    ev.status = "pending_review"
    db.commit()
    return _event_dict(ev)


@router.post("/email-events/{event_id}/undo")
def undo(event_id: int, db: Session = Depends(get_db)) -> dict[str, Any]:
    ev = _get_event(db, event_id)
    ok = undo_event(db, ev)
    if not ok:
        raise HTTPException(status_code=400, detail="No hay cambio de estado que deshacer")
    return _event_dict(ev)

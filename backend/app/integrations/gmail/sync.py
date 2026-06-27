"""Orquestacion de una sincronizacion de Gmail -> EmailEvents -> pipeline."""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.integrations.gmail import store
from app.integrations.gmail.base import GmailClient
from app.integrations.gmail.classifier import classify
from app.integrations.gmail.clients import get_client
from app.integrations.gmail.pipeline import process_email
from app.integrations.gmail.query import build_query, normalize_company, passes_prefilter
from app.models.email_event import EmailEvent
from app.models.job import Job

logger = logging.getLogger(__name__)


def run_sync(db: Session, client: GmailClient | None = None) -> dict[str, Any]:
    """Ejecuta una sincronizacion. Devuelve un resumen. No lanza si no hay conexion."""
    client = client or get_client()
    if client is None:
        return {"connected": False, "fetched": 0, "processed": 0, "applied": 0, "pending_review": 0}

    jobs = db.execute(select(Job)).scalars().all()
    companies = [j.company for j in jobs if j.company]
    companies_norm = {normalize_company(c) for c in companies if c}

    query = build_query(companies[:50], settings.gmail_lookback_days)
    messages = client.fetch_recent(query, max_results=50)

    processed = applied = pending = 0
    for msg in messages:
        if not msg.gmail_id:
            continue
        # Dedupe ANTES de clasificar (ahorra tokens).
        exists = db.execute(
            select(EmailEvent.id).where(EmailEvent.gmail_id == msg.gmail_id)
        ).first()
        if exists:
            continue
        if not passes_prefilter(msg.from_email, msg.subject, msg.snippet, companies_norm):
            continue

        classified = classify(msg)
        event = process_email(db, msg, classified, getattr(client, "account", ""))
        if event is None:
            continue
        processed += 1
        if event.status in ("auto_applied", "applied"):
            applied += 1
        elif event.status == "pending_review":
            pending += 1

    store.set_last_sync()
    summary = {
        "connected": True,
        "fetched": len(messages),
        "processed": processed,
        "applied": applied,
        "pending_review": pending,
    }
    logger.info("gmail sync: %s", summary)
    return summary

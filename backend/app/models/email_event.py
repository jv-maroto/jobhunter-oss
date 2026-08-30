"""Modelo EmailEvent (Pilar 4: tracking por Gmail).

Un registro por correo procesado. NO se persiste el cuerpo del correo, solo
un snippet corto (<=512 chars) y la salida del clasificador. Local-first y
solo-lectura: nunca se borra ni modifica correo del usuario.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class EmailEvent(Base):
    __tablename__ = "email_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    gmail_id: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    thread_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    account: Mapped[str] = mapped_column(String(256), default="")

    application_id: Mapped[int | None] = mapped_column(
        ForeignKey("applications.id", ondelete="SET NULL"), nullable=True
    )
    job_id: Mapped[int | None] = mapped_column(
        ForeignKey("jobs.id", ondelete="SET NULL"), nullable=True, index=True
    )

    # rechazo | invitacion_entrevista | peticion_info | oferta | acuse_recibo | irrelevante
    type: Mapped[str] = mapped_column(String(32), default="irrelevante", index=True)
    company: Mapped[str | None] = mapped_column(String(256), nullable=True)
    from_email: Mapped[str | None] = mapped_column(String(256), nullable=True)
    from_name: Mapped[str | None] = mapped_column(String(256), nullable=True)
    subject: Mapped[str | None] = mapped_column(String(512), nullable=True)
    snippet: Mapped[str | None] = mapped_column(String(512), nullable=True)
    received_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, index=True)

    # domain | company | ia | none
    match_method: Mapped[str] = mapped_column(String(16), default="none")
    match_confidence: Mapped[float] = mapped_column(Float, default=0.0)
    classified_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    # pending_review | applied | auto_applied | dismissed | no_change
    status: Mapped[str] = mapped_column(String(32), default="pending_review", index=True)
    applied_status_change: Mapped[str | None] = mapped_column(String(64), nullable=True)
    previous_job_status: Mapped[str | None] = mapped_column(String(32), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)

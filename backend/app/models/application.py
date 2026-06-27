"""Modelo Application (historial de aplicaciones)."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class Application(Base):
    __tablename__ = "applications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("jobs.id", ondelete="CASCADE"), index=True)
    cv_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    cover_letter_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    cv_content: Mapped[str | None] = mapped_column(Text, nullable=True)
    cover_letter_content: Mapped[str | None] = mapped_column(Text, nullable=True)
    language: Mapped[str] = mapped_column(String(8), default="en")
    status: Mapped[str] = mapped_column(String(32), default="prepared")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Automatizacion de aplicar (Pilar 3). En DBs existentes estas columnas se
    # crean via el mini-migrador ensure_columns() de db.init_db().
    # extension | mcp | playwright | manual
    provider: Mapped[str | None] = mapped_column(String(32), nullable=True)
    apply_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    screening_answers: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    job = relationship("Job", back_populates="applications")

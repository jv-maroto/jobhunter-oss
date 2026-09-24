"""Modelo Application (historial de aplicaciones)."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text, event, inspect, select
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
    cv_source_filename: Mapped[str | None] = mapped_column(String(256), nullable=True)
    cv_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    cv_mode: Mapped[str | None] = mapped_column(String(16), nullable=True)
    job_snapshot: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    job = relationship("Job", back_populates="applications")


@event.listens_for(Application, "before_insert")
def capture_job_snapshot(_mapper, connection, target):
    """Freeze the listing on new application versions, including extension flows."""
    from app.models.job import Job

    if target.job_snapshot is not None:
        return
    fields = ("title", "company", "location", "description", "source_url", "remote",
              "salary_min", "salary_max", "currency", "salary_period", "employment_type")
    row = connection.execute(select(*(getattr(Job, field) for field in fields)).where(
        Job.id == target.job_id
    )).mappings().first()
    if row is not None:
        target.job_snapshot = {**dict(row), "captured_at": datetime.now(timezone.utc).isoformat()}


@event.listens_for(Application, "before_update")
def protect_job_snapshot(_mapper, _connection, target):
    history = inspect(target).attrs.job_snapshot.history
    if history.has_changes() and history.deleted and history.deleted[0] is not None:
        raise ValueError("La instantánea de una candidatura no se puede sobrescribir")

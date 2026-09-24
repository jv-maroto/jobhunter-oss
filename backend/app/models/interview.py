from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class Interview(Base):
    __tablename__ = "interviews"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    application_id: Mapped[int | None] = mapped_column(ForeignKey("applications.id", ondelete="SET NULL"), nullable=True, index=True)
    job_snapshot: Mapped[dict] = mapped_column(JSON)
    cv_content: Mapped[str | None] = mapped_column(Text, nullable=True)
    cover_letter_content: Mapped[str | None] = mapped_column(Text, nullable=True)
    stage: Mapped[str] = mapped_column(String(20), default="screening")
    language: Mapped[str] = mapped_column(String(2), default="es")
    scheduled_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    notes: Mapped[str] = mapped_column(Text, default="")
    feedback: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(20), default="planned")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    prep_status: Mapped[str] = mapped_column(String(20), default="idle")
    prep_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    prep_input: Mapped[dict | None] = mapped_column(JSON(none_as_null=True), nullable=True)
    prep_result: Mapped[dict | None] = mapped_column(JSON(none_as_null=True), nullable=True)
    prep_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    prep_started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    prep_finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

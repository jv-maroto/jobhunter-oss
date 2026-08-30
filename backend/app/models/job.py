"""Modelo Job y cache de scoring."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    JSON,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Origen / identidad
    source: Mapped[str] = mapped_column(String(64), index=True)
    source_url: Mapped[str] = mapped_column(String(1024))
    source_id: Mapped[str | None] = mapped_column(String(256), nullable=True, index=True)
    hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)

    # Contenido
    title: Mapped[str] = mapped_column(String(512))
    company: Mapped[str] = mapped_column(String(256), index=True)
    company_id: Mapped[int | None] = mapped_column(ForeignKey("companies.id"), nullable=True)
    location: Mapped[str] = mapped_column(String(256), default="")
    remote: Mapped[bool] = mapped_column(default=False)
    salary_min: Mapped[float | None] = mapped_column(Float, nullable=True)
    salary_max: Mapped[float | None] = mapped_column(Float, nullable=True)
    currency: Mapped[str | None] = mapped_column(String(8), nullable=True)
    posted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    description: Mapped[str] = mapped_column(Text, default="")
    tags: Mapped[list[str] | None] = mapped_column(JSON, nullable=True, default=list)

    # Classification (dev vs sysadmin track) + salary heuristic
    track: Mapped[str] = mapped_column(String(16), default="dev", index=True)
    predicted_salary_band: Mapped[str] = mapped_column(
        String(16), default="unknown", index=True
    )

    # Scoring
    match_score: Mapped[float] = mapped_column(Float, default=0.0, index=True)
    salary_in_range: Mapped[bool | None] = mapped_column(default=None, nullable=True)
    remote_compatible: Mapped[bool | None] = mapped_column(default=None, nullable=True)
    location_compatible: Mapped[bool | None] = mapped_column(default=None, nullable=True)
    rejection_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    key_matches: Mapped[list[str] | None] = mapped_column(JSON, default=list)
    missing_skills: Mapped[list[str] | None] = mapped_column(JSON, default=list)
    personalization_hooks: Mapped[list[str] | None] = mapped_column(JSON, default=list)

    # Pipeline
    status: Mapped[str] = mapped_column(String(32), default="detected", index=True)
    applied_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    cv_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    cover_letter_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    company_obj = relationship("Company", back_populates="jobs", lazy="joined")
    applications = relationship("Application", back_populates="job", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_jobs_status_score", "status", "match_score"),
    )


class ScoreCache(Base):
    """Cache local de scoring para no re-llamar Haiku con la misma oferta."""

    __tablename__ = "score_cache"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    job_hash: Mapped[str] = mapped_column(String(64), index=True)
    cv_version: Mapped[str] = mapped_column(String(32), default="1")
    result_json: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    __table_args__ = (UniqueConstraint("job_hash", "cv_version", name="uq_score_cache_hash_cv"),)

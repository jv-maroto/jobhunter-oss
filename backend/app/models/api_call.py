"""Modelo SQLAlchemy para registrar llamadas a APIs de LLM (cost tracking)."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class ApiCall(Base):
    """Registro de una llamada a un provider LLM."""

    __tablename__ = "api_calls"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, index=True
    )
    provider: Mapped[str] = mapped_column(String(32), index=True)
    model: Mapped[str] = mapped_column(String(128))
    tier: Mapped[str] = mapped_column(String(32), index=True)
    input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0)
    cached_input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    cost_eur: Mapped[float] = mapped_column(Float, default=0.0)
    cached: Mapped[bool] = mapped_column(Boolean, default=False)

    __table_args__ = (
        Index("ix_api_calls_provider_tier", "provider", "tier"),
        Index("ix_api_calls_created_provider", "created_at", "provider"),
    )

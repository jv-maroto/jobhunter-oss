"""Registered public company boards with a bounded review inventory."""
from datetime import datetime

from sqlalchemy import JSON, DateTime, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class CompanyBoard(Base):
    __tablename__ = "company_boards"
    __table_args__ = (UniqueConstraint("provider", "slug", name="uq_company_board_provider_slug"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(160))
    provider: Mapped[str] = mapped_column(String(16))
    slug: Mapped[str] = mapped_column(String(100))
    status: Mapped[str] = mapped_column(String(16), default="active")
    staged_jobs: Mapped[list] = mapped_column(JSON, default=list)
    last_refresh: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

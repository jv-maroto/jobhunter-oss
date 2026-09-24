"""Persistent campaigns independent from legacy global search preferences."""
from datetime import datetime

from sqlalchemy import JSON, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class SearchCampaign(Base):
    __tablename__ = "search_campaigns"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(160))
    roles: Mapped[list] = mapped_column(JSON, default=list)
    countries: Mapped[list] = mapped_column(JSON, default=list)
    modality: Mapped[str] = mapped_column(String(16), default="any")
    languages: Mapped[list] = mapped_column(JSON, default=list)
    residence_country: Mapped[str | None] = mapped_column(String(2), nullable=True)
    max_queries: Mapped[int] = mapped_column(Integer, default=8)
    results_per_query: Mapped[int] = mapped_column(Integer, default=20)
    status: Mapped[str] = mapped_column(String(16), default="draft", index=True)
    last_run: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

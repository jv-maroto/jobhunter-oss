from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class CareerSource(Base):
    __tablename__ = "career_sources"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    url: Mapped[str] = mapped_column(String(2048), unique=True)
    owner_url: Mapped[str] = mapped_column(String(2048), index=True)
    kind: Mapped[str] = mapped_column(String(40))
    status: Mapped[str] = mapped_column(String(20))
    content_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    content_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    fetched_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    truncated: Mapped[bool] = mapped_column(default=False)
    active: Mapped[bool] = mapped_column(default=True)


class CareerSourceRefresh(Base):
    __tablename__ = "career_source_refresh"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    status: Mapped[str] = mapped_column(String(20), default="idle")
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)

"""Modelo Post LinkedIn."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, Date, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class Post(Base):
    __tablename__ = "posts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    date: Mapped[datetime | None] = mapped_column(Date, nullable=True, index=True)
    topic: Mapped[str] = mapped_column(String(256))
    content: Mapped[str] = mapped_column(Text)
    image_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    image_prompt: Mapped[str | None] = mapped_column(Text, nullable=True)
    hashtags: Mapped[list[str] | None] = mapped_column(JSON, default=list)
    status: Mapped[str] = mapped_column(String(32), default="draft", index=True)
    # "personal" = devlog/CV-driven · "trending" = current-news commentary
    kind: Mapped[str] = mapped_column(String(16), default="personal", index=True)
    # Source article URL when kind="trending" (Hacker News / dev.to / etc.)
    source_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    # Short summary of the linked article (og:description or first paragraph)
    source_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Structured metadata for the image renderer (og:image URL, style hints).
    # For trending posts this drives the AMD-style banner template.
    image_meta: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    scheduled_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

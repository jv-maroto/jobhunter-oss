"""LinkedIn feed posts captured by the Chrome extension."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Float, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class FeedPost(Base):
    """A post seen on the LinkedIn feed.

    Captured by the extension when the user scrolls the feed. Used to surface
    relevant posts where commenting (with a thoughtful, Claude-generated draft)
    is high-leverage networking.
    """

    __tablename__ = "feed_posts"
    __table_args__ = (UniqueConstraint("post_url", name="uq_feed_posts_url"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    post_url: Mapped[str] = mapped_column(String(512), index=True)
    author_name: Mapped[str | None] = mapped_column(String(256))
    author_headline: Mapped[str | None] = mapped_column(String(512))
    author_url: Mapped[str | None] = mapped_column(String(512))
    content_excerpt: Mapped[str | None] = mapped_column(Text)
    suggested_comment: Mapped[str | None] = mapped_column(Text)
    relevance_score: Mapped[float] = mapped_column(Float, default=0.0)
    language: Mapped[str | None] = mapped_column(String(8))
    status: Mapped[str] = mapped_column(String(24), default="new", index=True)
    # status: new | suggested | commented | skipped
    captured_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    commented_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

"""Modelo ApplyQueueItem (cola de aplicaciones para la extension).

La extension Chrome consume esta cola (GET /ext/apply-queue) y reporta el
resultado (POST /ext/applied). Patron espejo de la cola /ext/tasks que ya
usa la extension para las conexiones de LinkedIn.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class ApplyQueueItem(Base):
    __tablename__ = "apply_queue"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("jobs.id", ondelete="CASCADE"), index=True)
    application_id: Mapped[int | None] = mapped_column(
        ForeignKey("applications.id", ondelete="SET NULL"), nullable=True
    )

    platform: Mapped[str] = mapped_column(String(64), default="")
    apply_url: Mapped[str] = mapped_column(String(1024), default="")
    # queued | filled | submitted | needs_manual | failed | skipped
    status: Mapped[str] = mapped_column(String(32), default="queued", index=True)
    materials: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

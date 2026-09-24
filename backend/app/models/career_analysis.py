from datetime import datetime

from sqlalchemy import JSON, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class CareerAnalysis(Base):
    __tablename__ = "career_analyses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    status: Mapped[str] = mapped_column(String(20), default="queued", index=True)
    source_snapshot: Mapped[dict] = mapped_column(JSON)
    result: Mapped[dict | None] = mapped_column(JSON(none_as_null=True), nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

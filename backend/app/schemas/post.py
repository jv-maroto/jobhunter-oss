"""Schemas Pydantic para Posts."""

from __future__ import annotations

from datetime import date as date_t
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

PostStatus = Literal["draft", "scheduled", "published"]
PostKind = Literal["personal", "trending"]


class PostOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    date: date_t | None = None
    topic: str
    content: str
    image_path: str | None = None
    image_prompt: str | None = None
    hashtags: list[str] = Field(default_factory=list)
    status: PostStatus
    kind: PostKind = "personal"
    source_url: str | None = None
    scheduled_at: datetime | None = None
    published_at: datetime | None = None
    created_at: datetime


class PostPatch(BaseModel):
    status: PostStatus | None = None
    scheduled_at: datetime | None = None
    content: str | None = None


class PostGenerateIn(BaseModel):
    theme: str = "weekly mix"
    count: int = 21
    language: Literal["es", "en"] = "es"


class TrendingGenerateIn(BaseModel):
    count: int = 10
    language: Literal["es", "en"] = "es"
    replace_drafts: bool = False  # if true, deletes existing draft 'trending' posts first

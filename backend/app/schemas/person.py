"""Schemas Pydantic para Persons."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict

PersonStatus = Literal["pending", "queued", "sent", "accepted", "ignored"]


class PersonOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    full_name: str
    headline: str
    company: str | None = None
    profile_url: str
    reason: str
    message: str
    status: PersonStatus
    priority: int
    created_at: datetime


class PersonPatch(BaseModel):
    status: PersonStatus | None = None
    notes: str | None = None

"""Schemas Pydantic para Jobs."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

JobStatus = Literal[
    "detected", "prepared", "applied", "interviewing", "offer", "rejected", "ghosted"
]
JobTrack = Literal["dev", "sysadmin"]
SalaryBand = Literal["high", "mid", "low", "unknown"]


class ScrapedJob(BaseModel):
    """Job recien scrapeado, aun no normalizado en DB."""

    source: str
    source_url: str
    source_id: str | None = None
    title: str
    company: str
    location: str = ""
    remote: bool = False
    salary_min: float | None = None
    salary_max: float | None = None
    currency: str | None = None
    posted_at: datetime | None = None
    description: str = ""
    tags: list[str] = Field(default_factory=list)
    hash: str = ""  # Calculado por base.py


class ScoredJobResult(BaseModel):
    """Output del scorer Haiku."""

    match_score: int = Field(ge=0, le=100)
    salary_in_range: bool | None = None
    remote_compatible: bool | None = None
    location_compatible: bool | None = None
    key_matches: list[str] = Field(default_factory=list)
    missing_skills: list[str] = Field(default_factory=list)
    rejection_reason: str | None = None
    personalization_hooks: list[str] = Field(default_factory=list)


class JobOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    source: str
    source_url: str
    title: str
    company: str
    location: str
    remote: bool
    salary_min: float | None = None
    salary_max: float | None = None
    currency: str | None = None
    posted_at: datetime | None = None
    description: str
    track: JobTrack = "dev"
    predicted_salary_band: SalaryBand = "unknown"
    match_score: float
    rejection_reason: str | None = None
    key_matches: list[str] = Field(default_factory=list)
    missing_skills: list[str] = Field(default_factory=list)
    personalization_hooks: list[str] = Field(default_factory=list)
    status: JobStatus
    applied_at: datetime | None = None
    cv_path: str | None = None
    cover_letter_path: str | None = None
    created_at: datetime


class JobsListOut(BaseModel):
    total: int
    items: list[JobOut]


class JobPatch(BaseModel):
    status: JobStatus | None = None
    notes: str | None = None
    applied_at: datetime | None = None


class PrepareApplicationOut(BaseModel):
    job_id: int
    cv_path: str
    cover_letter_path: str
    cv_content: str
    cover_letter_content: str
    language: str

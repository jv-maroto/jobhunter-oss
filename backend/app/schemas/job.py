"""Schemas Pydantic para Jobs."""

from __future__ import annotations

from datetime import datetime, timezone
from ipaddress import ip_address
from typing import Literal
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from pydantic import BaseModel, ConfigDict, Field, field_serializer, field_validator

JobStatus = Literal[
    "detected", "prepared", "applied", "interviewing", "offer", "rejected", "ghosted"
]
JobTrack = Literal[
    "data_engineer", "data_analyst", "data_scientist", "analytics_eng", "bi",
    "ai_ml", "quant", "dev", "sysadmin",
]
SalaryPeriod = Literal["year", "month", "week", "day", "hour"]
EmploymentType = Literal["permanent", "temporary", "contract", "internship", "apprenticeship", "full_time", "part_time"]
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
    salary_period: SalaryPeriod | None = None
    employment_type: EmploymentType | None = None
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
    employment_compatible: bool | None = None
    seniority_compatible: bool | None = None
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
    salary_period: SalaryPeriod | None = None
    employment_type: EmploymentType | None = None
    salary_in_range: bool | None = None
    remote_compatible: bool | None = None
    location_compatible: bool | None = None
    employment_compatible: bool | None = None
    seniority_compatible: bool | None = None
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
    notes: str | None = None
    next_action: str | None = None
    next_action_at: datetime | None = None
    saved_by_user: bool = False
    qualification_assessment: dict | None = None
    created_at: datetime

    @field_serializer("applied_at", "next_action_at", "posted_at", "created_at", when_used="json")
    def serialize_utc(self, value: datetime | None) -> str | None:
        if value is None:
            return None
        return (value if value.tzinfo else value.replace(tzinfo=timezone.utc)).isoformat()


class JobsListOut(BaseModel):
    total: int
    items: list[JobOut]


class JobPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: JobStatus | None = None
    notes: str | None = Field(default=None, max_length=20000)
    applied_at: datetime | None = None
    application_id: int | None = Field(default=None, ge=1)
    next_action: str | None = Field(default=None, max_length=2000)
    next_action_at: datetime | None = None

    @field_validator("applied_at", "next_action_at")
    @classmethod
    def utc_dates(cls, value: datetime | None) -> datetime | None:
        if value is not None and value.tzinfo is not None:
            return value.astimezone(timezone.utc).replace(tzinfo=None)
        return value


def canonical_job_url(value: str) -> str:
    parsed = urlsplit(value)
    host = (parsed.hostname or "").lower().rstrip(".").encode("idna").decode("ascii")
    port = parsed.port
    if ":" in host:
        host = f"[{host}]"
    if port is not None and (parsed.scheme.lower(), port) not in (("http", 80), ("https", 443)):
        host += f":{port}"
    query = sorted((key, val) for key, val in parse_qsl(parsed.query, keep_blank_values=True)
                   if not key.lower().startswith("utm_") and key.lower() not in {"gclid", "fbclid"})
    return urlunsplit((parsed.scheme.lower(), host, parsed.path.rstrip("/") or "/", urlencode(query), ""))


class JobImport(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    title: str = Field(min_length=1, max_length=512)
    company: str = Field(min_length=1, max_length=256)
    description: str = Field(min_length=1, max_length=100000)
    url: str | None = Field(default=None, max_length=1024)
    location: str = Field(default="", max_length=256)
    remote: bool = Field(default=False, strict=True)

    @field_validator("url")
    @classmethod
    def public_job_url(cls, value: str | None) -> str | None:
        if not value:
            return None
        if any(char.isspace() for char in value) or "\\" in value:
            raise ValueError("Job URL must not contain whitespace or backslashes")
        try:
            parsed = urlsplit(value)
            host = (parsed.hostname or "").rstrip(".")
            if parsed.scheme.lower() not in {"http", "https"} or not host or parsed.username is not None or parsed.password is not None:
                raise ValueError("Job URL must be an HTTP(S) URL without credentials")
            if parsed.port is not None and not 1 <= parsed.port <= 65535:
                raise ValueError("Invalid URL port")
            try:
                address = ip_address(host)
            except ValueError:
                labels = host.encode("idna").decode("ascii").split(".")
                if (len(labels) < 2 or labels[-1].isdigit()
                        or host.lower().endswith((".localhost", ".local", ".internal", ".lan", ".home"))
                        or any(not label or not label[0].isalnum() or not label[-1].isalnum()
                               or any(not char.isalnum() and char != "-" for char in label)
                               for label in labels)):
                    raise ValueError("Job URL must use a public host") from None
            else:
                if not address.is_global:
                    raise ValueError("Job URL must use a public host")
            return canonical_job_url(value)
        except (UnicodeError, ValueError) as exc:
            raise ValueError(str(exc)) from exc


class JobImportOut(BaseModel):
    job: JobOut
    created: bool


class CvProvenance(BaseModel):
    mode: str
    source_filename: str | None = None
    sha256: str
    language: str


class PrepareApplicationOut(BaseModel):
    application_id: int
    job_id: int
    cv_path: str
    cover_letter_path: str
    cv_content: str
    cover_letter_content: str
    language: str
    cv_provenance: CvProvenance

"""Schemas del perfil de busqueda (Pilar 2)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.schemas.job import EmploymentType


class PlatformInfo(BaseModel):
    id: str
    label: str
    method: str
    countries: list[str] = Field(default_factory=list)
    apply_support: str = ""
    tos_risk: str = ""
    enabled_by_default: bool = False
    implemented: bool = False
    status: str = "available"
    requires_env: str | None = None
    notes: str | None = None


class SearchProfileOut(BaseModel):
    search_preferences: dict
    regions: list[str]
    queries_preview: list[str]
    active_platforms: list[PlatformInfo]
    suggested_platforms: list[PlatformInfo]


class SearchProfileIn(BaseModel):
    """Patch parcial de search_preferences. Solo se aplican los campos provistos."""

    model_config = ConfigDict(extra="allow")

    region_preset: Literal["all_europe", "only_spain", "only_switzerland", "remote_worldwide", "custom"] | None = None
    regions: list[str] | None = Field(default=None, max_length=32)
    platforms: dict[str, bool] | None = None
    roles: list[str] | None = Field(default=None, max_length=30)
    employment_types: list[EmploymentType] | None = None
    seniority: Literal["junior", "mid", "senior", "lead"] | None = None
    residence_country: str | None = None
    queries_auto: bool | None = None
    queries: list[str] | None = Field(default=None, max_length=100)
    max_queries: int | None = Field(default=None, ge=1, le=100)
    results_per_query: int | None = Field(default=None, ge=1, le=100)
    hours_old: int | None = Field(default=None, ge=1, le=8760)
    salary_min: int | None = Field(default=None, ge=0)
    salary_max: int | None = Field(default=None, ge=0)
    salary_currency: str | None = Field(default=None, pattern=r"^[A-Z]{3}$")
    salary_min_eur: int | None = Field(default=None, ge=0)
    salary_max_eur: int | None = Field(default=None, ge=0)
    remote_only: bool | None = None
    exclude_keywords: list[str] | None = None
    work_authorization_eu: bool | None = None
    willing_to_relocate: bool | None = None

    @field_validator("regions")
    @classmethod
    def validate_regions(cls, value: list[str] | None) -> list[str] | None:
        from app.scrapers.country_map import COUNTRY_MAP
        if value is None:
            return None
        result = list(dict.fromkeys(r.strip().upper() for r in value))
        if any(r not in {*COUNTRY_MAP, "EU", "REMOTE"} for r in result):
            raise ValueError("Unsupported search region")
        return result

    @field_validator("roles", "queries")
    @classmethod
    def clean_terms(cls, value: list[str] | None) -> list[str] | None:
        if value is None:
            return None
        out = []
        seen = set()
        for term in value:
            term = term.strip()
            if not term or len(term) > 160:
                raise ValueError("Search terms must contain 1 to 160 characters")
            if term.casefold() not in seen:
                seen.add(term.casefold())
                out.append(term)
        return out

    @model_validator(mode="after")
    def validate_salary_range(self):
        for low, high in ((self.salary_min, self.salary_max), (self.salary_min_eur, self.salary_max_eur)):
            if low is not None and high is not None and high < low:
                raise ValueError("Maximum salary must be at least the minimum salary")
        return self

"""Schemas del perfil de busqueda (Pilar 2)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class PlatformInfo(BaseModel):
    id: str
    label: str
    method: str
    countries: list[str] = Field(default_factory=list)
    apply_support: str = ""
    tos_risk: str = ""
    enabled_by_default: bool = False
    # ¿Hay un scraper detras de verdad? Si es False, activarla no busca nada.
    implemented: bool = False
    # "available" | "planned" (declarada, sin scraper) | "apply_only" (solo autorrelleno)
    status: str = "available"
    # Clave de entorno necesaria (p.ej. adzuna_app_id); si falta, se autodesactiva.
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

    region_preset: str | None = None
    regions: list[str] | None = None
    platforms: dict[str, bool] | None = None
    residence_country: str | None = None
    queries_auto: bool | None = None
    queries: list[str] | None = None
    max_queries: int | None = None
    results_per_query: int | None = None
    hours_old: int | None = None
    salary_min_eur: int | None = None
    salary_max_eur: int | None = None
    remote_only: bool | None = None
    exclude_keywords: list[str] | None = None
    work_authorization_eu: bool | None = None
    willing_to_relocate: bool | None = None

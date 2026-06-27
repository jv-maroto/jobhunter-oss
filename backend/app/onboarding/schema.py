"""Contratos Pydantic del perfil (cv_master.json) y de los fragmentos de onboarding.

Son deliberadamente permisivos (`extra="allow"`): el cv_master ha sido siempre
un JSON flexible y muchos consumidores (ext.py, cover_letter.py, scoring) leen
campos opcionales con defaults. Estos modelos sirven para VALIDAR antes de
escribir, no para recortar datos del usuario.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class _Loose(BaseModel):
    model_config = ConfigDict(extra="allow")


class PersonalInfo(_Loose):
    name: str = ""
    title: str = ""
    email: str = ""
    phone: str = ""
    location: str = ""
    location_short: str = ""
    city: str = ""
    country: str = ""
    github: str = ""
    linkedin: str = ""
    portfolio: str = ""
    availability: str = ""


class SearchPreferences(_Loose):
    # --- existentes ---
    salary_min_eur: int = 30000
    salary_max_eur: int = 50000
    remote_only: bool = False
    exclude_keywords: list[str] = Field(default_factory=list)
    preferred_countries: list[str] = Field(default_factory=list)  # LEGACY -> regions

    # --- (P2) seleccion de paises/plataformas ---
    region_preset: str | None = None  # all_europe | only_spain | remote_worldwide | custom
    regions: list[str] = Field(default_factory=list)  # ISO-3166-1 alpha-2 + "EU"/"REMOTE"
    residence_country: str = ""
    platforms: dict[str, bool] = Field(default_factory=dict)
    queries_auto: bool = True
    queries: list[str] = Field(default_factory=list)
    max_queries: int = 8
    results_per_query: int = 20
    hours_old: int = 72

    # --- (P1) campos que ext.py ya consume ---
    work_authorization_eu: bool = False
    willing_to_relocate: bool = False
    remote_preference: str = ""
    notice_period: str = ""
    salary_expectation: str = ""
    languages_text: str = ""


class CvMaster(_Loose):
    """Estructura completa del perfil unico. Validacion no destructiva."""

    personal: PersonalInfo = Field(default_factory=PersonalInfo)
    summary_es: str = ""
    summary_en: str = ""
    years_experience: float | int | None = None
    languages: list[dict] = Field(default_factory=list)
    experience: list[dict] = Field(default_factory=list)
    education: list[dict] = Field(default_factory=list)
    certifications: list[dict] = Field(default_factory=list)
    skills: dict[str, list[str]] = Field(default_factory=dict)
    projects: list[dict] = Field(default_factory=list)
    projects_highlight: list[dict] = Field(default_factory=list)
    narratives: dict[str, str] = Field(default_factory=dict)
    search_preferences: SearchPreferences = Field(default_factory=SearchPreferences)


class ProfileFragment(_Loose):
    """Fragmento parcial aportado por una fuente del onboarding (github/linkedin/cv).

    `source` identifica la procedencia para los badges de la pantalla de revision.
    """

    source: str = ""  # github | linkedin | cv | extension | manual
    personal: dict = Field(default_factory=dict)
    summary_es: str = ""
    summary_en: str = ""
    languages: list[dict] = Field(default_factory=list)
    experience: list[dict] = Field(default_factory=list)
    education: list[dict] = Field(default_factory=list)
    certifications: list[dict] = Field(default_factory=list)
    skills: dict[str, list[str]] = Field(default_factory=dict)
    projects: list[dict] = Field(default_factory=list)
    raw_text: str = ""  # texto extraido sin estructurar (CV/PDF), util para la fusion LLM

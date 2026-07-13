"""Pydantic Settings centralizadas."""

from __future__ import annotations

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuracion global cargada desde .env."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Anthropic (legacy aliases mantenidos por compatibilidad)
    anthropic_api_key: str = Field(default="")
    claude_haiku_model: str = Field(default="claude-haiku-4-5-20251001")
    claude_sonnet_model: str = Field(default="claude-sonnet-4-6")

    # ---- Multi-provider LLM ----
    # Orden de providers por tier (coma-separado).
    llm_scoring_tier: str = Field(default="anthropic-haiku,gemini-flash,ollama-qwen")
    llm_generation_tier: str = Field(default="anthropic-sonnet,gemini-pro,ollama-qwen")
    llm_messaging_tier: str = Field(default="anthropic-haiku,gemini-flash,ollama-qwen")

    # Credenciales adicionales
    gemini_api_key: str = Field(default="")
    ollama_base_url: str = Field(default="http://localhost:11434")

    # Modelos por slot
    anthropic_scoring_model: str = Field(default="claude-haiku-4-5-20251001")
    anthropic_generation_model: str = Field(default="claude-sonnet-4-6")
    gemini_scoring_model: str = Field(default="gemini-2.5-flash")
    gemini_generation_model: str = Field(default="gemini-2.5-pro")
    ollama_model: str = Field(default="qwen2.5:7b")

    # ---- IA: OpenAI + modo (fase 2) ----
    openai_api_key: str = Field(default="")
    openai_scoring_model: str = Field(default="gpt-4o-mini")
    openai_generation_model: str = Field(default="gpt-4o")
    # auto: cloud si hay clave -> Ollama local -> nada (scraping basico sin IA).
    ai_mode: str = Field(default="auto")  # auto | cloud | local | off
    ai_cloud_provider: str = Field(default="anthropic")  # anthropic | openai | gemini
    ai_scraping_enabled: bool = Field(default=False)  # queries IA + re-rank de resultados

    # DB
    database_url: str = Field(default="sqlite:///./jobhunter.db")

    # Logging
    log_level: str = Field(default="info")

    # Scheduler
    scrape_interval_hours: int = Field(default=6)
    enable_scheduler: bool = Field(default=True)

    # Scoring
    min_score_for_prepare: int = Field(default=70)

    # Feature flags — can be turned off in .env for the public version of the repo
    # (community user who only wants the job-search core without AI post/comment generation)
    enable_post_generation: bool = Field(default=True)
    enable_image_generation: bool = Field(default=True)
    enable_comment_suggestions: bool = Field(default=True)
    enable_trending_news: bool = Field(default=True)

    # ---- Onboarding (Pilar 1) ----
    onboarding_marker_path: str = Field(default="./data/.onboarded")
    onboarding_draft_path: str = Field(default="./data/onboarding_draft.json")
    # PAT opcional: sube el rate-limit de la API publica de GitHub (60->5000/h).
    github_token: str = Field(default="")

    # ---- Plataformas / search profile (Pilar 2) ----
    # Claves de APIs de portales (opcionales; el scraper se autodesactiva si faltan).
    reed_api_key: str = Field(default="")
    france_travail_client_id: str = Field(default="")
    france_travail_client_secret: str = Field(default="")
    bundesagentur_api_key: str = Field(default="")

    # ---- Automatizacion / MCP (Pilar 3) — todo OFF por defecto ----
    mcp_linkedin_enabled: bool = Field(default=False)
    mcp_linkedin_args: str = Field(default="linkedin-mcp-server")
    linkedin_cookie: str = Field(default="")  # li_at; vacio => deshabilitado
    mcp_linkedin_rate_per_hour: int = Field(default=20)
    mcp_jobspy_enabled: bool = Field(default=False)
    apply_playwright_enabled: bool = Field(default=False)
    apply_playwright_daily_cap: int = Field(default=5)
    apply_daily_cap: int = Field(default=30)  # tope global de aplicaciones/dia

    # ---- Gmail tracking (Pilar 4) — opcional, solo lectura ----
    enable_gmail_tracking: bool = Field(default=False)
    gmail_sync_interval_minutes: int = Field(default=30)
    gmail_lookback_days: int = Field(default=7)
    gmail_auto_apply_threshold: float = Field(default=0.8)
    gmail_match_threshold: float = Field(default=0.6)
    gmail_scope: str = Field(default="readonly")  # readonly | metadata

    # Paths
    data_dir: str = Field(default="./data")
    cv_master_path: str = Field(default="./app/data/cv_master.json")
    cv_template_path: str = Field(default="./app/data/cv_template.typ")
    platforms_catalog_path: str = Field(default="./app/scrapers/platforms.json")

    # CORS
    cors_origins: str = Field(default="http://localhost:3000,http://localhost:5173")
    # ID de la extensión Chrome de JobHunter. Si se define, solo esa extensión
    # puede llamar a la API (recomendado). Si se deja vacío, se permite cualquier
    # chrome-extension:// — cómodo para desarrollo pero deja que otras extensiones
    # instaladas en el navegador lean la API local.
    chrome_extension_id: str = Field(default="")

    @property
    def cors_origin_list(self) -> list[str]:
        base = [o.strip() for o in self.cors_origins.split(",") if o.strip()]
        # Si hay un extension ID configurado, se añade su origen exacto aquí y
        # se desactiva el regex comodín en main.py.
        ext_id = self.chrome_extension_id.strip()
        if ext_id:
            base.append(f"chrome-extension://{ext_id}")
        return base

    @property
    def cors_extension_regex(self) -> str | None:
        """Regex de origen para la extensión, o None si hay un ID exacto fijado."""
        return None if self.chrome_extension_id.strip() else r"chrome-extension://.*"

    @property
    def data_path(self) -> Path:
        p = Path(self.data_dir).resolve()
        p.mkdir(parents=True, exist_ok=True)
        (p / "applications").mkdir(exist_ok=True)
        (p / "posts").mkdir(exist_ok=True)
        (p / "cache").mkdir(exist_ok=True)
        return p

    @property
    def cv_master_file(self) -> Path:
        return Path(self.cv_master_path).resolve()

    @property
    def cv_template_file(self) -> Path:
        return Path(self.cv_template_path).resolve()

    @property
    def platforms_catalog_file(self) -> Path:
        return Path(self.platforms_catalog_path).resolve()

    @property
    def onboarding_marker_file(self) -> Path:
        return Path(self.onboarding_marker_path).resolve()

    @property
    def onboarding_draft_file(self) -> Path:
        return Path(self.onboarding_draft_path).resolve()

    @property
    def integrations_path(self) -> Path:
        """Carpeta local para credenciales de integraciones (Gmail, etc.)."""
        p = self.data_path / "integrations"
        p.mkdir(parents=True, exist_ok=True)
        return p


settings = Settings()

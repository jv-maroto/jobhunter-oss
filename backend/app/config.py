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

    # Paths
    data_dir: str = Field(default="./data")
    cv_master_path: str = Field(default="./app/data/cv_master.json")
    cv_template_path: str = Field(default="./app/data/cv_template.typ")

    # CORS
    cors_origins: str = Field(default="http://localhost:3000,http://localhost:5173")

    @property
    def cors_origin_list(self) -> list[str]:
        base = [o.strip() for o in self.cors_origins.split(",") if o.strip()]
        # Permite tambien la extension Chrome via regex aparte en main.py
        return base

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


settings = Settings()

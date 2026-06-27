"""Tipos comunes de la capa de aplicar."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class ApplyMode(str, Enum):
    extension = "extension"  # primario para ATS: rellena, el user pulsa Enviar
    mcp = "mcp"  # solo descubrir/leer (no envia)
    playwright = "playwright"  # submit automatico opcional, OFF por defecto
    manual = "manual"  # fallback universal


class ApplyStatus(str, Enum):
    queued = "queued"
    submitted = "submitted"
    needs_manual = "needs_manual"
    failed = "failed"
    skipped = "skipped"


@dataclass
class ApplyMaterials:
    cv_path: str | None = None
    cover_letter_path: str | None = None
    language: str = "en"

    def as_dict(self) -> dict:
        return {
            "cv_path": self.cv_path,
            "cover_letter_path": self.cover_letter_path,
            "language": self.language,
        }


@dataclass
class ApplyResult:
    mode: ApplyMode
    status: ApplyStatus
    job_id: int
    platform: str = ""
    application_id: int | None = None
    queue_id: int | None = None
    apply_url: str = ""
    message: str = ""

    def as_dict(self) -> dict:
        return {
            "mode": self.mode.value,
            "status": self.status.value,
            "job_id": self.job_id,
            "platform": self.platform,
            "application_id": self.application_id,
            "queue_id": self.queue_id,
            "apply_url": self.apply_url,
            "message": self.message,
        }


@dataclass
class JobLead:
    """Salida normalizada de un provider de descubrimiento (MCP/scraper)."""

    title: str
    company: str
    url: str
    location: str = ""
    description: str = ""
    source: str = "mcp"
    tags: list[str] = field(default_factory=list)

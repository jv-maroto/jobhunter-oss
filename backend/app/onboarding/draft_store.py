"""Almacen del borrador de onboarding (data/onboarding_draft.json).

Acumula los fragmentos aportados por cada fuente (github/linkedin/cv) de forma
idempotente y reintentable, mas el `merged` resultante de la fusion. Se borra
al completar el onboarding.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from app.config import settings
from app.profile_store import atomic_write_json

logger = logging.getLogger(__name__)


def _empty() -> dict[str, Any]:
    return {"fragments": {}, "merged": None}


def load_draft() -> dict[str, Any]:
    path = settings.onboarding_draft_file
    if not path.exists():
        return _empty()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        data.setdefault("fragments", {})
        data.setdefault("merged", None)
        return data
    except Exception as exc:  # noqa: BLE001
        raise ValueError("Unreadable onboarding draft; restore it before saving changes") from exc


def _write(data: dict[str, Any]) -> None:
    path = settings.onboarding_draft_file
    atomic_write_json(path, data)


def save_fragment(source: str, fragment: dict[str, Any]) -> dict[str, Any]:
    """Guarda/actualiza el fragmento de una fuente. Devuelve el draft completo."""
    data = load_draft()
    fragment = dict(fragment)
    fragment["source"] = source
    data["fragments"][source] = fragment
    data["merged"] = None  # invalida la fusion previa
    _write(data)
    return data


def get_fragments() -> dict[str, dict[str, Any]]:
    return load_draft().get("fragments", {})


def set_merged(cv_master: dict[str, Any], field_sources: dict, conflicts: list) -> None:
    data = load_draft()
    data["merged"] = {
        "cv_master": cv_master,
        "field_sources": field_sources,
        "conflicts": conflicts,
    }
    _write(data)


def clear_draft() -> None:
    path = settings.onboarding_draft_file
    if path.exists():
        try:
            path.unlink()
        except Exception as exc:  # noqa: BLE001
            logger.warning("no se pudo borrar el draft: %s", exc)


def start_from_profile(cv_master: dict[str, Any]) -> None:
    _write({"fragments": {}, "base": cv_master, "merged": {
        "cv_master": cv_master, "field_sources": {}, "conflicts": [],
    }})


def save_review(cv_master: dict[str, Any]) -> dict[str, Any]:
    data = load_draft()
    data["base"] = cv_master
    previous = data.get("merged") or {}
    if data.get("merged") is not None or not data.get("fragments"):
        data["merged"] = {"field_sources": {}, "conflicts": [], **previous, "cv_master": cv_master}
    _write(data)
    return data

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
        logger.warning("draft ilegible, reiniciando: %s", exc)
        return _empty()


def _write(data: dict[str, Any]) -> None:
    path = settings.onboarding_draft_file
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


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

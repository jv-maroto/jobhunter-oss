"""Deteccion de primer uso (sin auth, local-first).

`is_onboarded()` usa una triple senal para no re-disparar el wizard una vez
completado, ni considerar onboarded a una instancia que aun tiene el template:

1. Existe el marcador `data/.onboarded`  -> True (atajo rapido).
2. `cv_master.json` no existe / contiene `_README` / `personal.name` vacio o
   igual al placeholder del template ("Your Full Name") -> False.
3. En cualquier otro caso -> True.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime

from app.config import settings

logger = logging.getLogger(__name__)

_PLACEHOLDER_NAMES = {"", "your full name"}


def is_onboarded() -> bool:
    marker = settings.onboarding_marker_file
    if marker.exists():
        return True

    cv_path = settings.cv_master_file
    if not cv_path.exists():
        return False
    try:
        data = json.loads(cv_path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        logger.warning("cv_master ilegible al detectar onboarding: %s", exc)
        return False

    if "_README" in data:
        return False
    name = ((data.get("personal") or {}).get("name") or "").strip().lower()
    if name in _PLACEHOLDER_NAMES:
        return False
    return True


def mark_onboarded() -> None:
    """Crea el marcador `data/.onboarded` (idempotente)."""
    marker = settings.onboarding_marker_file
    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.write_text(datetime.utcnow().isoformat(), encoding="utf-8")
    logger.info("onboarding marcado como completado: %s", marker)

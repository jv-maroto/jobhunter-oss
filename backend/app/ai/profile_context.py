"""Datos del perfil del usuario para personalizar los recursos generados.

Existe para que la app NO lleve el perfil de nadie escrito a fuego. Antes los
generadores de imagenes traian los nombres de proyecto, el usuario de terminal y
las titulaciones del autor original hardcodeados: cualquiera que clonara el repo
acababa generando imagenes con los datos de otra persona.

Todo sale ahora de `cv_master.json` (que es de cada usuario y no se versiona),
con defaults genericos si falta el dato.
"""

from __future__ import annotations

import json
import logging
from functools import lru_cache
from typing import Any

from app.config import settings

logger = logging.getLogger(__name__)

DEFAULT_TERMINAL_LABEL = "dev@localhost ~ "
DEFAULT_BADGES: list[dict[str, str]] = [
    {"name": "Code", "color": "#cc785c"},
    {"name": "Cloud", "color": "#22d3ee"},
    {"name": "Linux", "color": "#a3e635"},
    {"name": "Python", "color": "#3776ab"},
]


@lru_cache(maxsize=1)
def _cv() -> dict[str, Any]:
    path = settings.cv_master_file
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        logger.warning("profile_context: cv_master ilegible: %s", exc)
        return {}


def cache_clear() -> None:
    """Llamar tras reescribir cv_master.json (settings / onboarding)."""
    _cv.cache_clear()


def project_keywords() -> list[str]:
    """Nombres de los proyectos del usuario, en minusculas.

    Se usan para clasificar un post como "project". Si el perfil no declara
    proyectos, devuelve [] y el clasificador simplemente no marca esa categoria.
    """
    cv = _cv()
    names: list[str] = []
    for key in ("projects_highlight", "projects"):
        for p in cv.get(key) or []:
            if isinstance(p, dict):
                name = p.get("name") or p.get("title")
            else:
                name = p
            if isinstance(name, str) and name.strip():
                names.append(name.strip().lower())
    return names


def terminal_label() -> str:
    """Etiqueta de la ventana de terminal en las imagenes: "nombre@host ~ "."""
    personal = _cv().get("personal") or {}
    name = (personal.get("name") or "").strip()
    handle = name.split()[0].lower() if name else ""
    if not handle:
        # De github.com/mi-usuario -> mi-usuario
        gh = (personal.get("github") or "").rstrip("/")
        handle = gh.split("/")[-1].lower() if gh else ""
    if not handle:
        return DEFAULT_TERMINAL_LABEL
    return f"{handle}@localhost ~ "


def career_badges() -> list[dict[str, str]]:
    """Chips de la imagen de categoria "career": titulaciones y skills del perfil."""
    cv = _cv()
    palette = ["#cc785c", "#22d3ee", "#a3e635", "#1ba0d7", "#3776ab", "#61dafb"]
    labels: list[str] = []

    for edu in (cv.get("education") or [])[:2]:
        if isinstance(edu, dict):
            label = edu.get("short") or edu.get("degree") or edu.get("title")
            if isinstance(label, str) and label.strip():
                labels.append(label.strip()[:14])

    for cert in (cv.get("certifications") or [])[:2]:
        label = cert.get("name") if isinstance(cert, dict) else cert
        if isinstance(label, str) and label.strip():
            labels.append(label.strip()[:14])

    skills = cv.get("skills") or {}
    if isinstance(skills, dict):
        for group in skills.values():
            for s in (group or [])[:1]:
                if isinstance(s, str) and s.strip():
                    labels.append(s.strip()[:14])

    if not labels:
        return DEFAULT_BADGES

    seen: set[str] = set()
    out: list[dict[str, str]] = []
    for i, label in enumerate(labels):
        low = label.lower()
        if low in seen:
            continue
        seen.add(low)
        out.append({"name": label, "color": palette[i % len(palette)]})
        if len(out) >= 6:
            break
    return out

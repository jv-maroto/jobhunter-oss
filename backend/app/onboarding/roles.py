"""Sugerencia de roles de trabajo a partir del perfil (cv_master).

Con IA (tier=generation) propone 1-4 roles realistas para buscar empleo. Sin IA,
heuristica determinista a partir de experience[].role + skills. Resultado: lista
de {id, label, why}. Estos roles se guardan luego en
cv_master.json::search_preferences.roles y los consume el query_builder.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

logger = logging.getLogger(__name__)

_ROLES_SYSTEM = """Eres un orientador laboral. A partir del PERFIL en JSON (experiencia,
skills, formacion) propones entre 1 y 4 ROLES de trabajo realistas para buscar empleo, en
el idioma del perfil. Para cada rol da:
- "label": titulo corto y profesional (p.ej. "Backend Developer", "DevOps Engineer",
  "Sysadmin", "Data Engineer").
- "why": una frase justificandolo con datos REALES del perfil.
NO inventes experiencia que no exista. Prioriza roles para los que el perfil esta
cualificado. Devuelve UNICAMENTE este JSON: {"roles": [{"label": "...", "why": "..."}]}"""


def _slug(label: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", (label or "").lower()).strip("-")
    return s or "role"


def _ai_available() -> bool:
    try:
        from app.ai.router import ai_available

        return ai_available()
    except Exception:  # noqa: BLE001
        return False


def _flatten_skills(cv: dict[str, Any]) -> list[str]:
    out: list[str] = []
    for vals in (cv.get("skills") or {}).values():
        if isinstance(vals, list):
            out.extend(str(v) for v in vals if v)
    return out


def _heuristic_roles(cv: dict[str, Any]) -> list[dict[str, str]]:
    cv = cv or {}
    out: list[dict[str, str]] = []
    seen: set[str] = set()

    for e in cv.get("experience") or []:
        role = str(e.get("role", "")).strip()
        if not role:
            continue
        key = role.lower()
        if key in seen:
            continue
        seen.add(key)
        company = str(e.get("company", "")).strip()
        why = f"Experiencia como {role}" + (f" en {company}." if company else ".")
        out.append({"id": _slug(role), "label": role, "why": why})
        if len(out) >= 4:
            break

    if not out:
        skills = _flatten_skills(cv)
        if skills:
            label = f"{skills[0]} Developer"
            out.append(
                {
                    "id": _slug(label),
                    "label": label,
                    "why": f"Stack principal basado en {', '.join(skills[:3])}.",
                }
            )

    if not out:
        out.append(
            {
                "id": "software-developer",
                "label": "Software Developer",
                "why": "Rol generico por defecto (perfil sin experiencia/skills).",
            }
        )
    return out[:4]


def suggest_roles(cv: dict[str, Any] | None) -> list[dict[str, str]]:
    """Devuelve 1-4 roles sugeridos como [{id, label, why}]."""
    cv = cv or {}
    if not _ai_available():
        logger.info("suggest_roles: sin IA, usando heuristica")
        return _heuristic_roles(cv)

    try:
        from app.ai.client import complete, parse_json_block

        compact = {
            "experience": [
                {
                    "role": e.get("role"),
                    "company": e.get("company"),
                    "highlights": (e.get("highlights") or [])[:3],
                }
                for e in (cv.get("experience") or [])[:8]
            ],
            "skills": cv.get("skills", {}),
            "education": cv.get("education", []),
            "summary": cv.get("summary_es") or cv.get("summary_en") or "",
        }
        raw = complete(
            tier="generation",
            system=_ROLES_SYSTEM,
            user="PERFIL:\n" + json.dumps(compact, ensure_ascii=False),
            max_tokens=600,
            temperature=0.4,
            json_mode=True,
        )
        data = parse_json_block(raw)
        roles_in = data.get("roles") if isinstance(data, dict) else None
        out: list[dict[str, str]] = []
        seen: set[str] = set()
        for r in roles_in or []:
            if not isinstance(r, dict):
                continue
            label = str(r.get("label", "")).strip()
            if not label or label.lower() in seen:
                continue
            seen.add(label.lower())
            out.append(
                {"id": _slug(label), "label": label, "why": str(r.get("why", "")).strip()}
            )
            if len(out) >= 4:
                break
        if out:
            return out
    except Exception as exc:  # noqa: BLE001
        logger.warning("suggest_roles IA fallo: %s; uso heuristica", exc)

    return _heuristic_roles(cv)

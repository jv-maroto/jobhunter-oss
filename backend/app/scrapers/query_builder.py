"""Construye las queries de busqueda a partir del perfil del usuario.

Sustituye a las listas hardcodeadas (`SEARCH_QUERIES`, `SYSADMIN_QUERIES`).
Deriva terminos de `experience[].role` + las skills mas relevantes del
`cv_master.json`. Si el usuario fija `queries_auto=false` y aporta `queries`,
se usan esas tal cual.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

# Fallback identico al comportamiento legacy de jobspy_scraper.SEARCH_QUERIES,
# usado solo cuando el perfil aun no tiene experiencia/skills (p.ej. template).
_LEGACY_FALLBACK = [
    "python developer remote",
    "fastapi",
    "ai engineer junior",
    "devops junior",
    "full stack python",
]


def _flatten_skills(skills: dict | None) -> list[str]:
    out: list[str] = []
    for vals in (skills or {}).values():
        if isinstance(vals, list):
            out.extend(str(v) for v in vals if v)
    return out


def build_search_queries(cv: dict | None, prefs: dict | None, max_n: int = 8) -> list[str]:
    cv = cv or {}
    prefs = prefs or {}

    # Override manual explicito.
    if prefs.get("queries_auto") is False and prefs.get("queries"):
        return [str(q) for q in prefs["queries"]][:max_n]

    max_n = int(prefs.get("max_queries", max_n) or max_n)

    roles = [
        str(e.get("role", "")).strip()
        for e in (cv.get("experience") or [])
        if e.get("role")
    ]
    skills = _flatten_skills(cv.get("skills"))

    queries: list[str] = []
    seen: set[str] = set()

    def _add(q: str) -> None:
        q = q.strip()
        key = q.lower()
        if q and key not in seen:
            seen.add(key)
            queries.append(q)

    # Roles tal cual + variante remota.
    for role in roles[:3]:
        _add(role)
        _add(f"{role} remote")

    # Skill principal como "<skill> developer".
    if skills:
        _add(f"{skills[0]} developer")
        if len(skills) > 1:
            _add(f"{skills[1]} developer")

    if not queries:
        logger.info("query_builder: perfil sin roles/skills, usando fallback legacy")
        return list(_LEGACY_FALLBACK)[:max_n]

    return queries[:max_n]

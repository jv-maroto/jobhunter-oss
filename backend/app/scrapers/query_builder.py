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
        return list(dict.fromkeys(str(q).strip() for q in prefs["queries"] if str(q).strip()))

    max_n = int(prefs.get("max_queries", max_n) or max_n)

    pref_roles = [str(r).strip() for r in (prefs.get("roles") or []) if str(r).strip()]
    exp_roles = [str(e.get("role", "")).strip() for e in (cv.get("experience") or []) if e.get("role")]
    roles = pref_roles or exp_roles
    queries = list(dict.fromkeys(roles))
    max_n = max(max_n, len(queries))
    if not queries:
        queries = _flatten_skills(cv.get("skills")) or list(_LEGACY_FALLBACK)
    base = queries[:max_n]

    # Scraping IA (opcional): enriquece las queries con variantes/idiomas via LLM.
    # Solo si el usuario lo activo (ai_scraping_enabled) y hay IA disponible.
    try:
        from app.config import settings

        if getattr(settings, "ai_scraping_enabled", False):
            from app.scrapers.ai_query import ai_expand_queries

            base = ai_expand_queries(cv, prefs, base, cap=max(max_n, 12))
    except Exception as exc:  # noqa: BLE001
        logger.warning("query_builder: expansion IA fallo: %s", exc)

    return base

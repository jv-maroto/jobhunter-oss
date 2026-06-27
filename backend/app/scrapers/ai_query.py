"""Expansion de queries de busqueda con IA (scraping IA).

Toma las queries base derivadas del perfil y, si hay IA disponible, las enriquece
con sinonimos del rol, combinaciones rol+skill y traducciones al idioma de las
regiones objetivo. Cap por defecto 12. Fallback: las base_queries tal cual.

Solo se invoca cuando settings.ai_scraping_enabled esta activo (lo decide el
query_builder); aqui ademas comprobamos que haya un LLM disponible.
"""

from __future__ import annotations

import json
import logging
from typing import Any

logger = logging.getLogger(__name__)

_QUERY_SYSTEM = """Eres un experto en busqueda de empleo. Dado un PERFIL (roles objetivo,
skills, regiones) y una lista de queries base, generas una lista AMPLIADA de queries de
busqueda efectivas para portales de empleo:
- sinonimos y variantes del rol,
- combinaciones rol + skill principal,
- traducciones al idioma de las regiones objetivo (ES/EN/DE/FR/SE...) cuando tenga sentido.
Queries cortas (2-5 palabras), sin comillas, sin operadores booleanos. Devuelve UNICAMENTE
este JSON: {"queries": ["...", "..."]}"""


def _ai_available() -> bool:
    try:
        from app.ai.router import ai_available

        return ai_available()
    except Exception:  # noqa: BLE001
        return False


def ai_expand_queries(
    cv: dict[str, Any] | None,
    prefs: dict[str, Any] | None,
    base_queries: list[str],
    cap: int = 12,
) -> list[str]:
    """Devuelve las base_queries enriquecidas con variantes IA (cap elementos).

    Las base_queries siempre van primero; las variantes IA se anaden detras y se
    deduplican. Sin IA o ante cualquier fallo, devuelve base_queries[:cap].
    """
    base = [str(q).strip() for q in (base_queries or []) if str(q).strip()]
    if not base or not _ai_available():
        return base[:cap]

    cv = cv or {}
    prefs = prefs or {}
    try:
        from app.ai.client import complete, parse_json_block

        skills: list[str] = []
        for vals in (cv.get("skills") or {}).values():
            if isinstance(vals, list):
                skills.extend(str(v) for v in vals if v)

        roles = prefs.get("roles") or [
            e.get("role") for e in (cv.get("experience") or []) if e.get("role")
        ]
        regions = prefs.get("regions") or prefs.get("preferred_countries") or []

        payload = {
            "roles": roles,
            "skills": skills[:20],
            "regions": regions,
            "base_queries": base,
        }
        raw = complete(
            tier="scoring",
            system=_QUERY_SYSTEM,
            user="DATOS:\n" + json.dumps(payload, ensure_ascii=False),
            max_tokens=400,
            temperature=0.5,
            json_mode=True,
        )
        data = parse_json_block(raw)
        generated = data.get("queries") if isinstance(data, dict) else None

        out: list[str] = []
        seen: set[str] = set()
        for q in list(base) + list(generated or []):
            q = str(q).strip()
            key = q.lower()
            if q and key not in seen:
                seen.add(key)
                out.append(q)
            if len(out) >= cap:
                break
        return out[:cap] if out else base[:cap]
    except Exception as exc:  # noqa: BLE001
        logger.warning("ai_expand_queries fallo: %s; uso base_queries", exc)
        return base[:cap]

"""Re-ranking de ofertas por relevancia con una pasada IA barata (scraping IA).

Reordena las primeras ~`limit` ofertas (solo title+company, sin descripcion para
abaratar) segun el perfil del usuario. Pasada unica y barata (tier=scoring). Las
ofertas mas alla de `limit` se conservan al final sin tocar. Fallback ante
cualquier fallo o sin IA: la lista original sin cambios.

Acepta objetos `ScrapedJob` (atributos) o dicts (claves).
"""

from __future__ import annotations

import json
import logging
from typing import Any

logger = logging.getLogger(__name__)

_RERANK_SYSTEM = """Eres un filtro de relevancia de ofertas de empleo. Recibes un PERFIL
(roles objetivo + skills) y una lista NUMERADA de ofertas (indice: titulo @ empresa).
Devuelves el ORDEN de los indices, de MAS a MENOS relevante para ese perfil. No inventes
ofertas ni indices nuevos; usa solo los indices dados. Devuelve UNICAMENTE este JSON:
{"order": [indice, ...]}"""


def _ai_available() -> bool:
    try:
        from app.ai.router import ai_available

        return ai_available()
    except Exception:  # noqa: BLE001
        return False


def _field(job: Any, name: str) -> str:
    if isinstance(job, dict):
        return str(job.get(name, "") or "")
    return str(getattr(job, name, "") or "")


def rerank_jobs(jobs: list[Any], cv: dict[str, Any] | None, limit: int = 40) -> list[Any]:
    """Reordena `jobs[:limit]` por relevancia; deja el resto al final intacto."""
    jobs = list(jobs or [])
    if len(jobs) <= 1 or not _ai_available():
        return jobs

    head = jobs[:limit]
    tail = jobs[limit:]
    cv = cv or {}
    try:
        from app.ai.client import complete, parse_json_block

        skills: list[str] = []
        for vals in (cv.get("skills") or {}).values():
            if isinstance(vals, list):
                skills.extend(str(v) for v in vals if v)

        prefs = cv.get("search_preferences", {}) if isinstance(cv, dict) else {}
        roles = (prefs or {}).get("roles") or [
            e.get("role") for e in (cv.get("experience") or []) if e.get("role")
        ]

        lines = [
            f"{i}: {_field(j, 'title')} @ {_field(j, 'company')}" for i, j in enumerate(head)
        ]
        user = (
            "PERFIL:\n"
            + json.dumps({"roles": roles, "skills": skills[:20]}, ensure_ascii=False)
            + "\n\nOFERTAS:\n"
            + "\n".join(lines)
        )
        raw = complete(
            tier="scoring",
            system=_RERANK_SYSTEM,
            user=user,
            max_tokens=800,
            temperature=0.0,
            json_mode=True,
        )
        data = parse_json_block(raw)
        order = data.get("order") if isinstance(data, dict) else None
        if not isinstance(order, list):
            return jobs

        seen: set[int] = set()
        reordered: list[Any] = []
        for idx in order:
            try:
                ii = int(idx)
            except (TypeError, ValueError):
                continue
            if 0 <= ii < len(head) and ii not in seen:
                seen.add(ii)
                reordered.append(head[ii])

        # Anade las que la IA no menciono, en su orden original.
        for i, j in enumerate(head):
            if i not in seen:
                reordered.append(j)

        return reordered + tail
    except Exception as exc:  # noqa: BLE001
        logger.warning("rerank_jobs fallo: %s; orden sin cambios", exc)
        return jobs

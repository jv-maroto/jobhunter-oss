"""Estructuracion de texto libre de CV/LinkedIn a la forma cv_master, con LLM.

Reusa el router LLM (tier=generation, json_mode). Degrada con elegancia: si no
hay ningun provider disponible, devuelve un fragmento minimo con el texto crudo
para que el usuario lo complete en la pantalla de revision (nunca inventa datos).
"""

from __future__ import annotations

import json
import logging
from typing import Any

from app.ai.client import complete, parse_json_block
from app.ai.router import get_router

logger = logging.getLogger(__name__)

_EXTRACT_SYSTEM = """Eres un parser de CVs. Recibes el TEXTO PLANO de un CV (o perfil de LinkedIn)
y devuelves UNICAMENTE un JSON con esta forma (omite lo que no aparezca; NO inventes nada):
{
  "personal": {"name","title","email","phone","location","location_short","github","linkedin","portfolio"},
  "summary_es": "", "summary_en": "",
  "languages": [{"name","level"}],
  "experience": [{"role","company","start","end","highlights":[]}],
  "education": [{"degree","institution","year"}],
  "certifications": [{"name","issuer","year"}],
  "skills": {"categoria": ["skill", ...]}
}
Reglas: copia datos textuales del CV, no los inventes ni los traduzcas; si un campo no
aparece, omitelo o dejalo vacio. `highlights` = bullets de logros. Responde solo el JSON."""


def llm_available() -> bool:
    try:
        return bool(get_router().available_providers("generation"))
    except Exception:  # noqa: BLE001
        return False


def structure_cv_text(text: str, source: str = "cv") -> dict[str, Any]:
    """Convierte texto plano de CV en un ProfileFragment estructurado.

    Sin LLM disponible -> fragmento con `raw_text` para revision manual.
    """
    text = (text or "").strip()
    if not text:
        return {"source": source, "raw_text": ""}

    if not llm_available():
        logger.info("profile_extractor: sin LLM, devolviendo raw_text para revision")
        return {"source": source, "raw_text": text[:20000]}

    try:
        raw = complete(
            tier="generation",
            system=_EXTRACT_SYSTEM,
            user="TEXTO DEL CV:\n" + text[:18000],
            max_tokens=4000,
            temperature=0.1,
            json_mode=True,
        )
        data = parse_json_block(raw)
        if not isinstance(data, dict):
            raise ValueError("respuesta no es objeto JSON")
        data["source"] = source
        return data
    except Exception as exc:  # noqa: BLE001
        logger.warning("profile_extractor LLM fallo: %s; devuelvo raw_text", exc)
        return {"source": source, "raw_text": text[:20000]}


_SUMMARY_SYSTEM = """Eres un redactor de perfiles profesionales. A partir del JSON de un perfil
(experiencia, skills, proyectos), redacta un resumen profesional breve (2-3 frases) que
destaque stack y experiencia real. NO inventes datos que no esten en el perfil.
Devuelve UNICAMENTE este JSON: {"summary_es": "...", "summary_en": "..."}"""


def generate_summaries(cv_master: dict[str, Any]) -> dict[str, str]:
    """Genera {summary_es, summary_en} a partir del cv_master. {} si no hay LLM/falla.

    NO toca ningun otro campo: la fusion determinista sigue siendo la autoridad
    para identidad/experiencia/skills/proyectos (el LLM es lossy con esos datos).
    """
    if not llm_available():
        return {}
    try:
        compact = {
            "experience": cv_master.get("experience", []),
            "skills": cv_master.get("skills", {}),
            "projects": cv_master.get("projects", [])[:5],
        }
        raw = complete(
            tier="generation",
            system=_SUMMARY_SYSTEM,
            user=json.dumps(compact, ensure_ascii=False),
            max_tokens=600,
            temperature=0.3,
            json_mode=True,
        )
        data = parse_json_block(raw)
        if isinstance(data, dict):
            return {
                "summary_es": str(data.get("summary_es", "")).strip(),
                "summary_en": str(data.get("summary_en", "")).strip(),
            }
    except Exception as exc:  # noqa: BLE001
        logger.warning("generate_summaries fallo: %s", exc)
    return {}

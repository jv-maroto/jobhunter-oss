"""Clasificador IA de correos de candidatura (tier=scoring / Haiku).

Degrada con elegancia: sin LLM disponible devuelve 'irrelevante' confidence 0.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from app.ai.client import complete, parse_json_block
from app.ai.router import get_router
from app.integrations.gmail.base import EmailMessage

logger = logging.getLogger(__name__)

TYPES = {
    "rechazo",
    "invitacion_entrevista",
    "peticion_info",
    "oferta",
    "acuse_recibo",
    "irrelevante",
}

_SYSTEM = """Clasificas correos relacionados con candidaturas de empleo. Devuelves UNICAMENTE
este JSON (sin texto extra):
{
  "type": "rechazo|invitacion_entrevista|peticion_info|oferta|acuse_recibo|irrelevante",
  "company": "nombre de la empresa o vacio",
  "company_domain": "dominio del remitente o vacio",
  "confidence": 0.0-1.0,
  "summary_es": "una frase resumen en espanol",
  "next_action_es": "que deberia hacer el candidato, una frase"
}
Reglas:
- "rechazo": descartan tu candidatura.
- "invitacion_entrevista": te citan/proponen entrevista o siguiente fase.
- "oferta": te ofrecen el puesto.
- "acuse_recibo": confirman que han recibido tu solicitud.
- "peticion_info": piden datos/test/disponibilidad.
- "irrelevante": newsletter, marketing, no relacionado con TUS candidaturas.
Si dudas, baja `confidence`. No inventes empresa si no aparece."""


def llm_available() -> bool:
    try:
        return bool(get_router().available_providers("scoring"))
    except Exception:  # noqa: BLE001
        return False


def classify(msg: EmailMessage) -> dict[str, Any]:
    if not llm_available():
        return {"type": "irrelevante", "company": "", "confidence": 0.0,
                "summary_es": "", "next_action_es": "", "company_domain": ""}

    user = json.dumps(
        {
            "from": f"{msg.from_name} <{msg.from_email}>",
            "subject": msg.subject,
            "body": (msg.body or msg.snippet or "")[:2000],
        },
        ensure_ascii=False,
    )
    try:
        raw = complete(
            tier="scoring",
            system=_SYSTEM,
            user=user,
            max_tokens=400,
            temperature=0.1,
            json_mode=True,
        )
        data = parse_json_block(raw)
    except Exception as exc:  # noqa: BLE001
        logger.warning("clasificador fallo: %s", exc)
        return {"type": "irrelevante", "company": "", "confidence": 0.0,
                "summary_es": "", "next_action_es": "", "company_domain": ""}

    t = str(data.get("type", "irrelevante")).strip().lower()
    if t not in TYPES:
        t = "irrelevante"
    try:
        conf = float(data.get("confidence", 0.0))
    except (TypeError, ValueError):
        conf = 0.0
    return {
        "type": t,
        "company": str(data.get("company", "") or ""),
        "company_domain": str(data.get("company_domain", "") or ""),
        "confidence": max(0.0, min(1.0, conf)),
        "summary_es": str(data.get("summary_es", "") or ""),
        "next_action_es": str(data.get("next_action_es", "") or ""),
    }

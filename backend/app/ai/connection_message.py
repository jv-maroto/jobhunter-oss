"""Generador de mensajes de conexion para LinkedIn.

Internamente usa el LLMRouter (tier=messaging) con fallback automatico.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from app.ai.client import run_sync
from app.ai.router import get_router

logger = logging.getLogger(__name__)

CONNECT_SYSTEM = """Eres un experto en redactar mensajes de conexion LinkedIn breves y autenticos.

Recibes:
- profile_owner: JSON con datos del que pide conexion.
- target_person: nombre, headline, empresa, rol.
- language: "es" o "en".

REGLAS:
- MAXIMO 280 caracteres (limite LinkedIn ~300).
- Mencionar algo concreto del target (rol, empresa, area).
- Mencionar 1 punto del perfil propio que sea relevante.
- Tono humano, NO copy-paste corporativo.
- Sin "Hope you're doing well" ni similares.
- Devolver UNICAMENTE el texto, sin comillas, sin firma."""


def _fallback_message(target: dict[str, Any], owner: dict[str, Any], language: str) -> str:
    company = target.get("company", "")
    role = target.get("headline", "")
    if language == "es":
        return (
            f"Hola, vi tu perfil ({role}) en {company}. Soy ingeniero Python+AI con proyectos "
            "en FastAPI y LLMs locales. Me encantaria conectar."
        )[:280]
    return (
        f"Hi, I saw your profile ({role}) at {company}. I'm a Python + AI engineer with FastAPI and "
        "local LLM projects. Would love to connect."
    )[:280]


def generate_connection_message(
    target_person: dict[str, Any],
    profile_owner: dict[str, Any],
    language: str = "es",
) -> str:
    """Devuelve un mensaje <300 chars personalizado."""
    router = get_router()
    if not router.available_providers("messaging"):
        return _fallback_message(target_person, profile_owner, language)

    try:
        user_prompt = (
            "profile_owner:\n" + json.dumps(profile_owner, ensure_ascii=False)
            + "\ntarget=" + json.dumps(target_person, ensure_ascii=False)
            + f"\nlanguage={language}"
        )
        response = run_sync(
            router.complete_for(
                tier="messaging",
                system=CONNECT_SYSTEM,
                user=user_prompt,
                max_tokens=400,
                temperature=0.5,
            )
        )
        text = response.content.strip().strip('"').strip("'")
        return text[:300]
    except Exception as exc:  # noqa: BLE001
        logger.exception("Connection msg via router fallido: %s", exc)
        return _fallback_message(target_person, profile_owner, language)

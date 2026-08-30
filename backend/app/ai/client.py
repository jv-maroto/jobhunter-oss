"""Cliente LLM unificado.

Antes era un wrapper sobre el SDK de Anthropic. Ahora es un fachada sobre `LLMRouter`
que soporta fallback automatico (Anthropic -> Gemini -> Ollama) por tier.

Mantenemos `get_anthropic_client()` y `parse_json_block()` por compatibilidad con
codigo que aun los importa directamente.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from functools import lru_cache
from typing import Any

from app.config import settings

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers compatibles con la API anterior
# ---------------------------------------------------------------------------


@lru_cache(maxsize=1)
def get_anthropic_client():  # type: ignore[no-untyped-def]
    """Cliente Anthropic singleton. Devuelve None si no hay API key.

    Conservado solo por compatibilidad. Codigo nuevo debe usar el router.
    """
    if not settings.anthropic_api_key:
        return None
    try:
        from anthropic import Anthropic  # type: ignore[import-not-found]

        return Anthropic(api_key=settings.anthropic_api_key)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Anthropic SDK no disponible: %s", exc)
        return None


def parse_json_block(text: str) -> dict[str, Any]:
    """Extrae el primer JSON valido del texto.

    Soporta:
    - JSON directo.
    - JSON envuelto en ```json ... ```.
    - JSON al principio + ruido despues.
    """
    text = text.strip()

    # Bloque markdown
    m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, flags=re.DOTALL)
    if m:
        try:
            return json.loads(m.group(1))
        except json.JSONDecodeError:
            pass

    # JSON directo
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Busca llave abierta hasta cierre balanceado
    start = text.find("{")
    if start < 0:
        raise ValueError(f"No JSON found in: {text[:200]}")
    depth = 0
    for i in range(start, len(text)):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                blob = text[start : i + 1]
                return json.loads(blob)
    raise ValueError(f"Unbalanced JSON: {text[:200]}")


# ---------------------------------------------------------------------------
# Helper sincrono que ejecuta una corrutina del router de forma segura
# desde codigo sincrono (los generadores actuales son sync).
# ---------------------------------------------------------------------------


def run_sync(coro):  # type: ignore[no-untyped-def]
    """Ejecuta una corrutina desde codigo sincrono.

    Si no hay loop corriendo, usa asyncio.run. Si hay (raro en este codebase
    sincrono), crea un hilo aparte para evitar nested-loop errors.
    """
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)

    # Hay loop activo: ejecuta en hilo aparte.
    import concurrent.futures

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(asyncio.run, coro)
        return future.result()


# ---------------------------------------------------------------------------
# Nueva API publica basada en el router.
# Las funciones existentes (generate_cv, generate_cover_letter, etc.) se exponen
# desde app.ai.__init__ y se han actualizado para llamar al router internamente.
# Aqui anadimos helpers "raw" por tier para casos nuevos.
# ---------------------------------------------------------------------------


async def acomplete(
    tier: str,
    system: str,
    user: str,
    max_tokens: int = 4096,
    temperature: float = 0.3,
    json_mode: bool = False,
    cache_system: bool = True,
) -> str:
    """Llama al router por tier y devuelve el contenido textual."""
    from app.ai.router import get_router

    response = await get_router().complete_for(
        tier=tier,
        system=system,
        user=user,
        max_tokens=max_tokens,
        temperature=temperature,
        json_mode=json_mode,
        cache_system=cache_system,
    )
    return response.content


def complete(
    tier: str,
    system: str,
    user: str,
    max_tokens: int = 4096,
    temperature: float = 0.3,
    json_mode: bool = False,
    cache_system: bool = True,
) -> str:
    """Version sincrona de `acomplete`."""
    return run_sync(
        acomplete(
            tier=tier,
            system=system,
            user=user,
            max_tokens=max_tokens,
            temperature=temperature,
            json_mode=json_mode,
            cache_system=cache_system,
        )
    )


# ---------------------------------------------------------------------------
# Firmas "limpias" pedidas por el spec. Son wrappers que delegan en los
# generadores reales (app/ai/cv_generator.py, etc.) o en el router.
# ---------------------------------------------------------------------------


async def generate_cv_content(
    cv_master: dict[str, Any],
    job: dict[str, Any],
    template: str,
    language: str = "es",
) -> str:
    """Genera el contenido Typst del CV usando el router (tier=generation)."""
    from app.ai.cv_generator import CV_SYSTEM

    user = (
        "cv_master:\n" + json.dumps(cv_master, ensure_ascii=False)
        + "\n\ncv_template:\n" + template
        + f"\n\nOferta (idioma={language}):\n"
        + json.dumps(
            {
                "title": job.get("title"),
                "company": job.get("company"),
                "description": (job.get("description") or "")[:5000],
            },
            ensure_ascii=False,
        )
    )
    return await acomplete(
        tier="generation",
        system=CV_SYSTEM,
        user=user,
        max_tokens=4000,
        temperature=0.3,
    )


async def generate_cover_letter(
    cv_master: dict[str, Any],
    job: dict[str, Any],
    personalization_hooks: list[str],
    language: str = "es",
) -> str:
    """Genera el texto de la carta de presentacion (tier=generation)."""
    from app.ai.cover_letter import COVER_SYSTEM

    user = (
        "cv_master:\n" + json.dumps(cv_master, ensure_ascii=False)
        + f"\n\nlanguage={language}"
        + "\nhooks=" + json.dumps(personalization_hooks, ensure_ascii=False)
        + "\noferta=" + json.dumps(
            {
                "title": job.get("title"),
                "company": job.get("company"),
                "location": job.get("location"),
                "description": (job.get("description") or "")[:4000],
            },
            ensure_ascii=False,
        )
    )
    return await acomplete(
        tier="generation",
        system=COVER_SYSTEM,
        user=user,
        max_tokens=1200,
        temperature=0.4,
    )


async def generate_post(
    profile: dict[str, Any],
    theme: str = "weekly mix",
    count: int = 7,
    language: str = "es",
) -> dict[str, Any]:
    """Genera posts semanales en JSON (tier=generation)."""
    from app.ai.post_generator import POST_SYSTEM

    user = (
        "profile:\n" + json.dumps(profile, ensure_ascii=False)
        + f"\ntheme={theme}\ncount={count}\nlanguage={language}"
    )
    raw = await acomplete(
        tier="generation",
        system=POST_SYSTEM,
        user=user,
        max_tokens=4000,
        temperature=0.7,
        json_mode=True,
    )
    return parse_json_block(raw)


async def generate_connection_message(
    target_person: dict[str, Any],
    profile_owner: dict[str, Any],
    language: str = "es",
) -> str:
    """Genera un mensaje de conexion <300 chars (tier=messaging)."""
    from app.ai.connection_message import CONNECT_SYSTEM

    user = (
        "profile_owner:\n" + json.dumps(profile_owner, ensure_ascii=False)
        + "\ntarget=" + json.dumps(target_person, ensure_ascii=False)
        + f"\nlanguage={language}"
    )
    text = await acomplete(
        tier="messaging",
        system=CONNECT_SYSTEM,
        user=user,
        max_tokens=400,
        temperature=0.5,
    )
    return text.strip().strip('"').strip("'")[:300]


async def score_job(
    cv_master: dict[str, Any],
    job: dict[str, Any],
) -> dict[str, Any]:
    """Devuelve el JSON crudo del scoring (tier=scoring)."""
    from app.scoring.prompts import SCORING_SYSTEM, build_scoring_user_prompt

    user = (
        "CV (referencia):\n" + json.dumps(cv_master, ensure_ascii=False)
        + "\n\n" + build_scoring_user_prompt({}, job)
    )
    raw = await acomplete(
        tier="scoring",
        system=SCORING_SYSTEM,
        user=user,
        max_tokens=800,
        temperature=0.2,
        json_mode=True,
    )
    return parse_json_block(raw)

"""Genera comentarios LinkedIn contextuales con Claude."""

from __future__ import annotations

import logging
from typing import Any

from app.ai.client import run_sync
from app.ai.router import get_router

logger = logging.getLogger(__name__)


SYSTEM_PROMPT = (
    "Escribes un comentario para LinkedIn en nombre de un ingeniero de software. "
    "El perfil concreto (nombre, stack, experiencia) llega en el user prompt.\n\n"
    "REGLAS ABSOLUTAS:\n"
    "- 1 o 2 frases. MÁXIMO 35 palabras. Nunca más.\n"
    "- Tono natural, como un mensaje en Slack a un colega. NO corporativo.\n"
    "- Una observación concreta sobre el contenido del post. Cero clichés.\n"
    "- NO emojis. NO hashtags. NO saludos ('hola', 'genial post', 'gracias por compartir'). "
    "NO frases huecas ('totalmente de acuerdo', 'muy interesante', 'qué reflexión').\n"
    "- NO te presentes ni metas tu CV. Estás opinando sobre el post.\n"
    "- Idioma del post (si es en español → en español; si es en inglés → en inglés).\n"
    "- Si el post es genérico, motivacional, ofertas de empleo o spam → devuelve cadena vacía.\n\n"
    "EJEMPLOS de buen estilo (en español):\n"
    "Post: 'Llevamos 6 meses con Kubernetes en producción y no volvería atrás.'\n"
    "Comentario: 'La parte buena es el día 200, no el día 1. Lo difícil es justificar la curva los primeros 3 meses.'\n\n"
    "Post: 'Los LLMs locales con Ollama ya están listos para empresa.'\n"
    "Comentario: '¿Qué modelo te aguantó mejor en contexto largo? Con Qwen 14B tuve buenos resultados en RAG, pero a partir de 32k tokens se ralentiza.'\n\n"
    "EJEMPLOS en inglés:\n"
    "Post: 'We replaced our cron jobs with Temporal and never looked back.'\n"
    "Comentario: 'Same here for retries with backoff, but the local dev story still feels heavier than plain cron. Did you keep both for quick scripts?'\n"
)


def _build_user_prompt(
    author_name: str,
    author_headline: str,
    content: str,
) -> str:
    return (
        f"Autor del post: {author_name} ({author_headline})\n\n"
        f"Contenido del post:\n{content[:1500]}\n\n"
        "Escribe SÓLO el comentario (1-2 frases, máximo 35 palabras). "
        "Sin preámbulos ni explicaciones ni comillas."
    )


def _post_process(text: str) -> str:
    """Recorta a 2 frases máximo y limpia comillas / preámbulos."""
    text = text.strip().strip('"').strip("'").strip()
    # Strip common preambles
    for prefix in ("Comentario:", "Comment:", "Respuesta:"):
        if text.lower().startswith(prefix.lower()):
            text = text[len(prefix):].strip()
    # Keep first 2 sentences max
    import re
    parts = re.split(r"(?<=[.!?])\s+", text)
    if len(parts) > 2:
        text = " ".join(parts[:2]).strip()
    return text


def generate_comment(
    cv_master: dict[str, Any],
    author_name: str,
    author_headline: str,
    content: str,
) -> tuple[str, float]:
    """Devuelve (comentario, relevance_score 0-1).
    Si el comentario es vacío, indica que el post no es relevante.
    """
    del cv_master  # ya no se inyecta el CV — distraía al modelo
    user_prompt = _build_user_prompt(author_name, author_headline, content)
    router = get_router()
    try:
        resp = run_sync(
            router.complete_for(
                tier="messaging",
                system=SYSTEM_PROMPT,
                user=user_prompt,
                max_tokens=120,  # ~80 palabras hard cap
                temperature=0.4,
            )
        )
    except Exception as e:
        logger.warning("comment generation failed: %s", e)
        return ("", 0.0)

    text = _post_process(resp.content or "")
    if not text or len(text) < 12:
        return ("", 0.0)

    # Relevance score: penaliza longitud (>200 chars resta), bonus si menciona stack.
    word_count = len(text.split())
    if word_count <= 30:
        score = 0.85
    elif word_count <= 45:
        score = 0.65
    else:
        score = 0.40
    keywords = ("python", "fastapi", "react", "docker", "ai", "llm", "ollama", "claude", "kubernetes", "ansible", "linux", "devops")
    if any(k in text.lower() for k in keywords):
        score = min(1.0, score + 0.1)
    return (text, round(score, 2))

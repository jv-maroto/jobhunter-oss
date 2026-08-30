"""Modulo de generacion AI (CV, carta, posts, mensajes).

Soporta multiples providers LLM con fallback automatico:
Anthropic (principal) -> Gemini (gratis) -> Ollama (local).
"""

from app.ai.client import (
    acomplete,
    complete,
    generate_cv_content,
    generate_post,
    get_anthropic_client,
    parse_json_block,
)
from app.ai.client import (
    generate_connection_message as generate_connection_message_via_router,
)
from app.ai.client import (
    generate_cover_letter as generate_cover_letter_via_router,
)
from app.ai.client import (
    score_job as score_job_via_router,
)
from app.ai.connection_message import generate_connection_message
from app.ai.cover_letter import generate_cover_letter
from app.ai.cv_generator import generate_cv
from app.ai.post_generator import generate_weekly_posts
from app.ai.router import LLMRouter, build_default_router, get_router, set_router

__all__ = [
    # firmas publicas existentes (compatibilidad)
    "generate_connection_message",
    "generate_cover_letter",
    "generate_cv",
    "generate_weekly_posts",
    "get_anthropic_client",
    "parse_json_block",
    # nuevas firmas / router
    "acomplete",
    "complete",
    "generate_cv_content",
    "generate_post",
    "generate_connection_message_via_router",
    "generate_cover_letter_via_router",
    "score_job_via_router",
    "LLMRouter",
    "build_default_router",
    "get_router",
    "set_router",
]

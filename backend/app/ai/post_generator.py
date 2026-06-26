"""Generador de posts LinkedIn semanales.

Internamente usa el LLMRouter (tier=generation) con fallback automatico.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from app.ai.client import parse_json_block, run_sync
from app.ai.router import get_router

logger = logging.getLogger(__name__)

POST_SYSTEM = """Eres un copywriter especializado en LinkedIn tecnico para perfiles full-stack + sysadmin + AI.

Recibes:
- profile: JSON con datos del autor (proyectos reales, stack).
- theme: tematica/serie de la semana.
- count: numero de posts (puede ser hasta 21 = 3 por dia x 7 dias).
- language: "es" o "en".

Mezcla obligatoria de areas (distribuye ~equilibradamente entre count posts):
- Python / FastAPI / backend patterns
- AI aplicada (LLMs locales con Ollama, embeddings, Whisper, YOLO)
- Sysadmin / DevOps (Linux scripts, Bash, Docker, monitorizacion, backups, Active Directory, Windows Server, networking L2/CCNA, hardening CIS)
- Frontend (React, TypeScript, Tailwind v4, Vite)
- Behind-the-scenes de proyectos reales del autor (usa `profile.projects_highlight` o `profile.experience` como fuente; si no hay datos, omite esta categoría)
- Lessons learned de incidencias reales (down, datos perdidos, deploys malos, debugging)
- Carrera y aprendizaje continuo (transiciones, certificaciones, estudios)

Devuelve JSON con la forma:
{
  "posts": [
    {
      "topic": "string",
      "category": "python|ai|sysadmin|frontend|project|career",
      "content": "post completo en markdown (200-600 palabras)",
      "hashtags": ["string", ...],
      "image_prompt": "descripcion CONCRETA para una imagen visual (no abstracta): si es codigo, indicar 'snippet con fondo oscuro mostrando X'. Si es diagrama, indicar componentes y conexiones. Si es metricas, indicar tipo de chart y ejes."
    }
  ]
}

REGLAS:
- Primera linea (hook) corta y fuerte, sin clickbait barato.
- Cuerpo: 5-15 lineas con valor REAL (snippet de codigo, comando bash, comando AD, lesson learned, tip practico). Si la categoria es sysadmin, prioriza comandos shell, scripts concretos, configuraciones de produccion.
- Hashtags 3-5, relevantes y especificos. Para sysadmin usa #Linux #Bash #Docker #SysAdmin #DevOps #ActiveDirectory etc. Para AI usa #LLM #Ollama #FastAPI #AI etc.
- No usar emojis decorativos. Si acaso, 1 max.
- Sin frases vacias tipo "Today I want to share...".
- Cada post debe poder leerse standalone.
- Anclar en proyectos/experiencia reales cuando aplique.
- Si count >= 14, alterna categorias agresivamente para no repetir tema.
- Devolver UNICAMENTE el JSON, sin markdown fences."""


class NoLLMAvailableError(RuntimeError):
    """No LLM provider is configured for the 'generation' tier."""


TRENDING_SYSTEM = """Eres copywriter de LinkedIn para un ingeniero de software.
El perfil concreto (nombre, stack, experiencia, proyectos) llega en el user
prompt en el campo `profile`. Adapta tono y referencias a ese perfil.

Recibes una lista de noticias tech reales (titulo + URL + summary + score + comentarios HN).
El campo `summary` es la descripción oficial del artículo (og:description) — úsalo
para escribir con conocimiento real del contenido, NO te inventes detalles.
Para CADA noticia, generas UN post de LinkedIn que comenta la noticia desde la
perspectiva técnica del autor (usa su stack y proyectos del profile como anclaje).

Devuelve JSON:
{
  "posts": [
    {
      "topic": "string — un titular fuerte para el post, NO copies el titular original",
      "category": "ai|python|sysadmin|frontend|project|career",
      "content": "markdown 150-350 palabras — hook + 2-3 frases sobre la noticia + opinión técnica concreta + por qué importa para devs/sysadmins + cierre",
      "hashtags": ["#3-5", "#hashtags", "#relevantes"],
      "source_url": "URL EXACTA de la noticia original",
      "image_prompt": "una frase concreta describiendo la imagen explicativa"
    }
  ]
}

REGLAS:
- Tono natural, NO corporativo. Como un dev hablando con otros devs.
- Hook directo en la primera línea (no "Today I want to talk about...").
- Aporta SIEMPRE valor encima de la noticia: comparación con stack alternativo, comando, snippet, lesson learned relacionada, predicción concreta.
- Si la noticia es sobre LLMs / AI, conecta con la experiencia en Ollama, RAG, embeddings.
- Si es sysadmin/devops, conecta con los 4 años en producción.
- NO emojis decorativos. 0-1 máximo.
- Hashtags específicos al tema, no genéricos tipo #tech #innovation.
- Idioma: español por defecto salvo que el campo `language` sea "en".
- Termina SIEMPRE el `content` con una línea final tipo: "🔗 Fuente: {source_url}" (sustituye {source_url} por la URL real). Esto da el link al artículo en el feed de LinkedIn.
- Devuelve ÚNICAMENTE el JSON, sin markdown fences."""


def generate_trending_posts(
    stories: list[dict[str, Any]],
    profile: dict[str, Any],
    language: str = "es",
) -> list[dict[str, Any]]:
    """Toma stories (de HN o similar) y genera 1 post por noticia."""
    router = get_router()
    if not router.available_providers("generation"):
        raise NoLLMAvailableError(
            "No LLM disponible. Verifica ANTHROPIC_API_KEY en .env."
        )
    if not stories:
        return []

    stories_block = json.dumps(
        [
            {
                "title": s["title"],
                "url": s["url"],
                "summary": s.get("summary", ""),
                "score": s.get("score", 0),
                "comments": s.get("comments", 0),
            }
            for s in stories
        ],
        ensure_ascii=False,
    )
    profile_block = json.dumps(profile, ensure_ascii=False)
    user_prompt = (
        f"language={language}\n\nprofile:\n{profile_block}\n\nstories:\n{stories_block}"
    )

    max_tokens = min(16000, max(2000, len(stories) * 800 + 800))
    try:
        response = run_sync(
            router.complete_for(
                tier="generation",
                system=TRENDING_SYSTEM,
                user=user_prompt,
                max_tokens=max_tokens,
                temperature=0.7,
                json_mode=True,
            )
        )
        posts = _parse_posts_tolerant(response.content)
        if not posts:
            raise RuntimeError("LLM returned no posts from trending stories")
        return posts[: len(stories)]
    except Exception as exc:
        logger.exception("Trending post gen failed: %s", exc)
        raise NoLLMAvailableError(f"La generación de posts trending falló: {exc}") from exc


def generate_weekly_posts(
    profile: dict[str, Any],
    theme: str = "weekly mix",
    count: int = 7,
    language: str = "es",
    avoid_topics: list[str] | None = None,
) -> list[dict[str, Any]]:
    """Devuelve lista de dicts {topic, content, hashtags, image_prompt}.

    `avoid_topics`: títulos de posts ya publicados/programados — Claude debe
    proponer temas distintos para no repetir.
    """
    router = get_router()
    if not router.available_providers("generation"):
        raise NoLLMAvailableError(
            "No LLM configurado para generación de posts. "
            "Verifica que ANTHROPIC_API_KEY esté en .env y que el backend "
            "se haya arrancado con `set -a && source .env && set +a` antes de uvicorn."
        )

    avoid_block = ""
    if avoid_topics:
        cleaned = [t.strip() for t in avoid_topics if t and t.strip()]
        cleaned = list(dict.fromkeys(cleaned))[:40]  # dedup + cap
        if cleaned:
            avoid_block = (
                "\n\nTEMAS YA PUBLICADOS — NO los repitas ni propongas variantes cercanas:\n"
                + "\n".join(f"- {t}" for t in cleaned)
            )

    try:
        user_prompt = (
            "profile:\n" + json.dumps(profile, ensure_ascii=False)
            + f"\ntheme={theme}\ncount={count}\nlanguage={language}"
            + avoid_block
        )
        # Each post is ~400-600 output tokens. Give Claude generous budget and
        # cap at Sonnet 4.6's max output (16k) so 21 posts fit comfortably.
        max_tokens = min(16000, max(2000, count * 700 + 800))
        response = run_sync(
            router.complete_for(
                tier="generation",
                system=POST_SYSTEM,
                user=user_prompt,
                max_tokens=max_tokens,
                temperature=0.75,  # higher temperature for variety
                json_mode=True,
            )
        )
        posts = _parse_posts_tolerant(response.content)
        if not posts:
            raise RuntimeError("LLM returned no posts (empty array or unparseable)")
        return posts[:count]
    except Exception as exc:
        logger.exception("Post gen via router fallido: %s", exc)
        raise NoLLMAvailableError(
            f"La llamada al LLM para generar posts falló: {exc}"
        ) from exc


def _parse_posts_tolerant(raw: str) -> list[dict[str, Any]]:
    """Parse JSON output. If truncated mid-array, recover whole post objects."""
    if not raw:
        return []
    # First attempt: clean parse
    try:
        parsed = parse_json_block(raw)
        posts = parsed.get("posts", [])
        if isinstance(posts, list) and posts:
            return posts
    except Exception:  # noqa: BLE001
        pass
    # Recovery: greedy extract each complete `{...}` object inside the posts array
    # by balancing braces. Stops at the first unbalanced fragment.
    recovered: list[dict[str, Any]] = []
    idx = raw.find('"posts"')
    if idx == -1:
        return []
    arr_start = raw.find("[", idx)
    if arr_start == -1:
        return []
    i = arr_start + 1
    n = len(raw)
    while i < n:
        # Skip whitespace and commas
        while i < n and raw[i] in " \n\r\t,":
            i += 1
        if i >= n or raw[i] != "{":
            break
        # Track braces with string-awareness
        depth = 0
        obj_start = i
        in_str = False
        escape_next = False
        while i < n:
            c = raw[i]
            if escape_next:
                escape_next = False
            elif c == "\\" and in_str:
                escape_next = True
            elif c == '"':
                in_str = not in_str
            elif not in_str:
                if c == "{":
                    depth += 1
                elif c == "}":
                    depth -= 1
                    if depth == 0:
                        chunk = raw[obj_start : i + 1]
                        try:
                            recovered.append(json.loads(chunk))
                        except Exception:  # noqa: BLE001
                            pass
                        i += 1
                        break
            i += 1
        else:
            # Reached end without closing brace — partial last object, discard
            break
    if recovered:
        logger.warning("Recovered %d posts from truncated JSON", len(recovered))
    return recovered

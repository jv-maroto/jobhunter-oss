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

POST_SYSTEM = """Redactas borradores profesionales de LinkedIn para el perfil proporcionado.

Recibes:
- profile: JSON con datos del autor (proyectos reales, stack).
- theme: tematica/serie de la semana.
- count: numero de posts (puede ser hasta 21 = 3 por dia x 7 dias).
- language: "es" o "en".

Mezcla de areas (distribuye ~equilibradamente entre count posts). IMPORTANTE:
las areas tecnicas SIEMPRE salen del perfil del autor (`profile.skills`,
`profile.experience`, `profile.projects_highlight`). NO inventes un stack ni
asumas tecnologias que no aparezcan en `profile`:
- Su area principal de backend/datos, segun `profile.skills`
- Su area de infra/devops, si la tiene
- Su area de frontend, si la tiene
- Behind-the-scenes de proyectos reales del autor (usa `profile.projects_highlight`
  o `profile.experience` como fuente; si no hay datos, omite esta categoría)
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
- No inventar incidentes, resultados, tecnologias, certificaciones ni experiencias personales.
- Conservar la distincion entre practicas, empleo, proyectos academicos y prototipos.
- Respetar claim_boundaries y context/context_detail; un objetivo de carrera no es un empleo previo.
- Si count >= 14, alterna categorias agresivamente para no repetir tema.
- Devolver UNICAMENTE el JSON, sin markdown fences."""


class NoLLMAvailableError(RuntimeError):
    """No LLM provider is configured for the 'generation' tier."""


TRENDING_SYSTEM = """Redactas borradores informativos de LinkedIn basados en fuentes verificables.
El perfil del autor (stack, proyectos) llega en `profile` — úsalo
solo como anclaje puntual, no divagues sobre él.

Recibes noticias tech reales (título + URL + summary + score + comentarios HN).
El `summary` es descripción real (og:description) — no inventes detalles.

PRIORIZACIÓN de qué noticias merecen post: entre las que recibas, prefiere las
que aportan informacion concreta y relevante para las areas del autor.
DESCARTA (devuelve menos posts) las noticias que son:
- Tutorials genéricos ("cómo hacer X con Y")
- Nicho muy técnico sin gancho general
- Meta-noticias sobre HN o Reddit
Es MEJOR devolver 8 posts fuertes que 15 mediocres.

Devuelve JSON:
{
  "posts": [
    {
      "topic": "titular corto, max 55 chars, con GANCHO (no copies el original)",
      "category": "ai|python|sysadmin|frontend|project|career",
      "content": "60-100 palabras — estructura obligatoria abajo",
      "hashtags": ["#3-5", "#hashtags", "#específicos"],
      "source_url": "URL EXACTA de la noticia original",
      "image_prompt": "una frase describiendo la imagen"
    }
  ]
}

ESTRUCTURA obligatoria del `content` (LinkedIn scroll-stopper):
- LÍNEA 1: frase breve de hasta 100 caracteres que resuma un hecho de la fuente.
- LÍNEA EN BLANCO
- 2-4 líneas de contexto (una idea por línea, corta). Puedes usar bullets con
  el carácter "→ " o "• " al principio (NO markdown `-`/`*`).
- LÍNEA EN BLANCO
- CTA final: pregunta abierta 1 línea que invite a comentar. Ejemplos:
    "¿Lo probarías en producción?"
    "¿Vale realmente la pena migrar?"
    "¿Qué pensáis?"
- LÍNEA EN BLANCO
- Última línea SIEMPRE: "🔗 Fuente: {source_url}" (con la URL real)

REGLAS estrictas:
- Máximo 100 palabras en total (contando fuente).
- NO frases largas — cada línea debe leerse en 2 segundos.
- Tono directo, casi de conversación. Cero corporativismo.
- 1 emoji funcional al inicio si aplica (🚨 breaking, 🤯 shock, 💰 dinero, 🧠 IA,
  ⚡ perf, 🔥 hot). Nunca decorativo, nunca en medio del texto.
- SIN markdown. Prohibido `**bold**`, `__bold__`, `*it*`, backticks, headers,
  listas con `-` o `*`. Enfatiza con MAYÚSCULAS ocasionales o saltos de línea.
- Hashtags específicos al tema (nombre del producto/tech), no genéricos.
- Idioma: `language` (es por defecto).
- Anclaje al perfil: solo una conexión cuando los hechos del perfil la sustenten.
- No inventar cifras, citas, consecuencias, experiencia personal ni uso de herramientas.
- Distinguir hechos de la fuente, opinion y limites de lo que se conoce.
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
    # Profile is identical across calls -> put it in the system prompt so
    # Anthropic's prompt caching (cache_control) can amortise it. The
    # anthropic provider auto-enables cache_control once the system crosses
    # the Haiku threshold; on Sonnet the threshold is 1024 tokens which the
    # profile easily meets. Cuts input cost ~60% on the 2nd+ call within 5min.
    profile_block = json.dumps(profile, ensure_ascii=False)
    system_prompt = (
        TRENDING_SYSTEM
        + "\n\nAuthor profile (identical across every trending call):\n"
        + profile_block
    )
    user_prompt = f"language={language}\n\nstories:\n{stories_block}"

    max_tokens = min(16000, max(2000, len(stories) * 800 + 800))
    try:
        response = run_sync(
            router.complete_for(
                tier="generation",
                system=system_prompt,
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
        # Profile is stable across every weekly generation -> system prompt
        # so prompt caching amortises it.
        system_prompt = (
            POST_SYSTEM
            + "\n\nAuthor profile (identical across weekly calls):\n"
            + json.dumps(profile, ensure_ascii=False)
        )
        user_prompt = (
            f"theme={theme}\ncount={count}\nlanguage={language}"
            + avoid_block
        )
        # Each post is ~400-600 output tokens. Give Claude generous budget and
        # cap at Sonnet 4.6's max output (16k) so 21 posts fit comfortably.
        max_tokens = min(16000, max(2000, count * 700 + 800))
        response = run_sync(
            router.complete_for(
                tier="generation",
                system=system_prompt,
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

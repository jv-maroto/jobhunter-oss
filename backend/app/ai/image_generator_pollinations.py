"""Generador de imagenes V4: Pollinations.ai (gratis, sin auth).

Pollinations expone GET https://image.pollinations.ai/prompt/{prompt} y devuelve
una PNG generada por Flux/SD. No requiere API key, sin rate limit estricto.

Construye un prompt de imagen rico basado en el topic + categoría del post.
"""

from __future__ import annotations

import logging
import re
import time
from pathlib import Path
from typing import Any
from urllib.parse import quote

import httpx

from app.ai import profile_context
from app.config import settings

logger = logging.getLogger(__name__)


WIDTH = 1200
HEIGHT = 628
ENDPOINT = "https://image.pollinations.ai/prompt/{prompt}"

# Style by category — keeps a consistent visual identity per topic.
STYLE_BY_CATEGORY: dict[str, str] = {
    "python": (
        "modern flat illustration, isometric programming setup, "
        "code editor and python snake logo subtle in background, "
        "blue and cyan palette, clean vector art, technical poster style, no text"
    ),
    "ai": (
        "futuristic minimalist illustration, neural network nodes, "
        "subtle glowing brain or robot silhouette, purple and pink palette, "
        "soft gradient background, vector art, no text"
    ),
    "sysadmin": (
        "minimal flat illustration, server rack with green status lights, "
        "terminal window and monitoring graph, green and amber palette, "
        "linux penguin subtle in background, vector art, no text"
    ),
    "frontend": (
        "modern flat illustration, browser window mockup with abstract UI, "
        "react logo subtle, orange and yellow palette, geometric shapes, "
        "vector art, no text"
    ),
    "project": (
        "editorial illustration, modern workspace with laptop and abstract data, "
        "cyan and lime accents, professional vector art, no text"
    ),
    "career": (
        "minimalist illustration, person climbing stairs metaphor or open door, "
        "lime and cyan palette, soft modern vector art, motivational mood, no text"
    ),
}


def _detect_category(content: str, category: str | None = None) -> str:
    if category and category.lower() in STYLE_BY_CATEGORY:
        return category.lower()
    text = content.lower()
    if any(k in text for k in ["ollama", "llm", "claude", "gpt", "whisper", "yolo", "pgvector"]):
        return "ai"
    if any(k in text for k in ["bash", "ssh", "active directory", "windows server", "rsync", "linux", "cron", "systemd"]):
        return "sysadmin"
    if any(k in text for k in ["react", "tailwind", "vite", "next.js", "tsx", "frontend"]):
        return "frontend"
    if any(k in text for k in ["fastapi", "django", "celery", "pydantic"]):
        return "python"
    projects = profile_context.project_keywords()
    if projects and any(k in text for k in projects):
        return "project"
    if any(k in text for k in ["entrevista", "carrera", "transición", "aprendí", "lección"]):
        return "career"
    return "project"


def _build_prompt(topic: str, content: str, category: str) -> str:
    style = STYLE_BY_CATEGORY[category]
    # Extract 2-3 key technical concepts to anchor the image
    keywords = []
    for kw in ["fastapi", "react", "docker", "ollama", "claude", "redis", "postgres",
               "celery", "whisper", "yolo", "bash", "linux", "windows server",
               "ad", "ssh", "stripe", "next.js", "tailwind"]:
        if kw in content.lower() or kw in topic.lower():
            keywords.append(kw)
        if len(keywords) >= 3:
            break

    keywords_str = ", ".join(keywords) if keywords else "modern tech stack"

    # Sanitize topic: remove emojis and special chars for cleaner prompt
    clean_topic = re.sub(r"[^\w\sáéíóúñÁÉÍÓÚÑ.,:-]", "", topic)[:80]

    prompt = (
        f"{style}, theme: {clean_topic.lower()}, "
        f"featuring {keywords_str}, dark background with subtle grid, "
        f"professional LinkedIn post header, 16:9 horizontal format, "
        f"high quality, detailed but minimalist, no humans, no faces"
    )
    return prompt


def generate_post_image_pollinations(
    post_id: int, post_data: dict[str, Any]
) -> Path | None:
    """Generate an image via Pollinations.ai. Returns saved path or None."""
    try:
        topic = (post_data.get("topic") or "").replace("[ext-error]", "").strip()
        content = (post_data.get("content") or "").replace("[ext-error]", "").strip()
        category = _detect_category(content, post_data.get("category"))

        out_dir = settings.data_path / "posts" / "images"
        out_dir.mkdir(parents=True, exist_ok=True)
        output_path = out_dir / f"post_{post_id}.png"

        prompt = _build_prompt(topic, content, category)
        # nologo=true removes the Pollinations watermark
        # model=flux uses the Flux model (default but explicit)
        # seed=<post_id> makes the image deterministic per post
        url = ENDPOINT.format(prompt=quote(prompt, safe=""))
        params = {
            "width": str(WIDTH),
            "height": str(HEIGHT),
            "model": "flux",
            "nologo": "true",
            "seed": str(post_id * 100 + 7),
        }

        logger.info("pollinations request for post %s: %s", post_id, prompt[:120])
        start = time.time()
        with httpx.Client(timeout=httpx.Timeout(60.0)) as client:
            resp = client.get(url, params=params, follow_redirects=True)
            resp.raise_for_status()
            content_type = resp.headers.get("content-type", "")
            if "image" not in content_type:
                logger.warning(
                    "pollinations returned non-image (%s) for post %s",
                    content_type,
                    post_id,
                )
                return None
            output_path.write_bytes(resp.content)
        elapsed = time.time() - start
        logger.info(
            "pollinations image saved for post %s in %.1fs: %s bytes",
            post_id,
            elapsed,
            output_path.stat().st_size,
        )
        return output_path
    except Exception as e:  # noqa: BLE001
        logger.exception(
            "generate_post_image_pollinations failed for %s: %s", post_id, e
        )
        return None

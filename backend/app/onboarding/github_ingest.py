"""Ingesta de perfil desde GitHub (API publica REST).

Extrae datos del usuario + sus repos mas relevantes (por stars) para derivar
skills (lenguajes) y proyectos destacados. Token opcional (settings.github_token)
solo para subir el rate-limit de 60 a 5000 req/h.
"""

from __future__ import annotations

import logging
import re
from collections import Counter
from typing import Any

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

API = "https://api.github.com"


def _username_from(value: str) -> str:
    value = (value or "").strip()
    m = re.search(r"github\.com/([^/?#]+)", value)
    if m:
        return m.group(1)
    return value.lstrip("@/")


def _headers() -> dict[str, str]:
    h = {"Accept": "application/vnd.github+json", "User-Agent": "jobhunter-onboarding"}
    if settings.github_token:
        h["Authorization"] = f"Bearer {settings.github_token}"
    return h


def fetch_github_fragment(username_or_url: str, max_repos: int = 6) -> dict[str, Any]:
    """Devuelve un ProfileFragment (dict) con personal/skills/projects desde GitHub.

    Lanza ValueError si el usuario no existe o la API falla de forma dura.
    """
    username = _username_from(username_or_url)
    if not username:
        raise ValueError("Username de GitHub vacio")

    with httpx.Client(timeout=20.0, headers=_headers(), follow_redirects=True) as client:
        ru = client.get(f"{API}/users/{username}")
        if ru.status_code == 404:
            raise ValueError(f"Usuario de GitHub no encontrado: {username}")
        ru.raise_for_status()
        user = ru.json()

        rr = client.get(
            f"{API}/users/{username}/repos",
            params={"sort": "pushed", "per_page": 100, "type": "owner"},
        )
        rr.raise_for_status()
        repos = [r for r in rr.json() if not r.get("fork")]

    # Lenguajes -> skills (ordenados por frecuencia).
    lang_counter: Counter[str] = Counter()
    for r in repos:
        if r.get("language"):
            lang_counter[r["language"]] += 1

    # Top repos por stars.
    repos_sorted = sorted(repos, key=lambda r: r.get("stargazers_count", 0), reverse=True)
    projects: list[dict[str, Any]] = []
    for r in repos_sorted[:max_repos]:
        projects.append(
            {
                "name": r.get("name", ""),
                "description": r.get("description") or "",
                "url": r.get("html_url", ""),
                "stars": r.get("stargazers_count", 0),
                "languages": [r["language"]] if r.get("language") else [],
                "source": "github",
            }
        )

    personal: dict[str, Any] = {"github": user.get("html_url", "")}
    if user.get("name"):
        personal["name"] = user["name"]
    if user.get("blog"):
        personal["portfolio"] = user["blog"]
    if user.get("location"):
        personal["location"] = user["location"]
        personal["location_short"] = user["location"]
    if user.get("email"):
        personal["email"] = user["email"]

    fragment: dict[str, Any] = {
        "source": "github",
        "personal": personal,
        "skills": {"languages_github": [lang for lang, _ in lang_counter.most_common(12)]},
        "projects": projects,
    }
    if user.get("bio"):
        fragment["summary_en"] = user["bio"]

    logger.info(
        "github: %s -> %d repos, %d langs, %d proyectos",
        username,
        len(repos),
        len(lang_counter),
        len(projects),
    )
    return fragment

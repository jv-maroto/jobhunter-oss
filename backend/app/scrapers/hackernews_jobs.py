"""Scraper del hilo mensual "Ask HN: Who is hiring?" (API Algolia, sin auth).

Cada mes el usuario `whoishiring` abre un hilo y cada comentario raiz es una
oferta. El formato convencional de la primera linea es:

    Empresa | Ubicacion | Puesto | REMOTE | Salario | contacto

No es un formato garantizado, asi que parseamos de forma defensiva: si no
podemos extraer empresa+puesto con confianza, descartamos el comentario en vez
de meter basura en la BD.

OJO: no confundir con `hacker_news.py`, que trae NOTICIAS para generar posts de
LinkedIn. Este modulo trae OFERTAS DE EMPLEO.
"""

from __future__ import annotations

import html
import logging
import re
from datetime import datetime

import httpx

from app.scrapers.base import BaseScraper
from app.schemas.job import ScrapedJob

logger = logging.getLogger(__name__)

_SEARCH_URL = "https://hn.algolia.com/api/v1/search_by_date"
_ITEM_URL = "https://hn.algolia.com/api/v1/items/{story_id}"

# Solo nos interesan ofertas tech relevantes; el hilo trae de todo.
_TECH_KEYWORDS = {
    "python", "fastapi", "django", "flask", "backend", "back-end",
    "frontend", "front-end", "fullstack", "full-stack", "full stack",
    "javascript", "typescript", "react", "node", "vue", "next.js",
    "devops", "sre", "infrastructure", "platform", "kubernetes", "docker",
    "linux", "sysadmin", "cloud", "aws", "gcp", "azure",
    "engineer", "developer", "programmer", "software",
    "ai", "ml", "machine learning", "llm", "data",
    "postgres", "sql", "golang", "rust", "java",
}

# Señales de remoto en la linea de cabecera.
_REMOTE_RE = re.compile(r"\bremote\b|\bremoto\b", re.IGNORECASE)
_ONSITE_ONLY_RE = re.compile(r"\bonsite\s*only\b|\bno\s*remote\b", re.IGNORECASE)
_TAG_RE = re.compile(r"<[^>]+>")

# El orden de los segmentos NO es fijo: hay cabeceras que ponen el salario antes
# que el puesto. Clasificamos cada segmento en vez de fiarnos de la posicion.
_SALARY_RE = re.compile(
    r"[$€£]|\b\d{2,3}\s*[-–]\s*\d{2,3}\s*k\b|\bk\+|\bequity\b|\bsalary\b|"
    r"\bcompensation\b|\bbenefits\b|\bstock\b",
    re.IGNORECASE,
)
_URL_RE = re.compile(r"https?://|\bwww\.|@", re.IGNORECASE)
_VISA_RE = re.compile(r"\bvisa\b|\bsponsor|\bfull[- ]?time\b|\bpart[- ]?time\b|\bcontract\b", re.IGNORECASE)
# Palabras que identifican un PUESTO (no un salario ni una ciudad).
_ROLE_RE = re.compile(
    r"\bengineer|\bdeveloper|\bdev\b|\bprogrammer|\barchitect|\bscientist|"
    r"\bdesigner|\banalyst|\badmin|\bsre\b|\bdevops\b|\blead\b|\bmanager\b|"
    r"\bfounder|\bcto\b|\bintern\b|\bresearcher|\bconsultant|\bspecialist|"
    r"\broles?\b|\bhiring\b|\bstack\b",
    re.IGNORECASE,
)
# Separadores usados en el hilo: pipe, guion largo, guion medio.
_SPLIT_RE = re.compile(r"\s*[|–—]\s*|\s+-\s+")


def _strip_html(raw: str) -> str:
    """HTML de HN -> texto plano (los <p> marcan parrafos)."""
    text = raw.replace("<p>", "\n").replace("</p>", "\n")
    text = _TAG_RE.sub("", text)
    return html.unescape(text).strip()


def _parse_header(header: str) -> tuple[str, str, str]:
    """Primera linea -> (empresa, ubicacion, puesto). Vacios si no hay confianza.

    Preferimos descartar una oferta antes que inventarnos el puesto: un titulo
    basura ("150-250k + equity") contamina la BD y ademas gasta una llamada de
    LLM al puntuarla.
    """
    parts = [p.strip() for p in _SPLIT_RE.split(header) if p.strip()]
    if len(parts) < 2:
        return "", "", ""

    company = parts[0]
    role = ""
    location = ""

    for p in parts[1:]:
        if _URL_RE.search(p):
            continue
        is_salary = bool(_SALARY_RE.search(p))
        is_remote = bool(_REMOTE_RE.search(p))

        # Puesto: suena a rol, y no es una linea de pasta ni de visado.
        if not role and _ROLE_RE.search(p) and not is_salary and not _VISA_RE.search(p):
            role = p
            continue
        # Ubicacion: menciona remoto, o es un fragmento corto tipo "NYC - hybrid".
        if not location and not is_salary and (is_remote or 1 <= len(p.split()) <= 4):
            location = p

    if not role:
        return "", "", ""  # sin puesto fiable -> fuera

    if not location:
        location = "Remote" if _REMOTE_RE.search(header) else ""
    return company, location, role


class HackerNewsWhoIsHiringScraper(BaseScraper):
    """Ofertas del hilo mensual "Who is hiring?" de Hacker News."""

    name = "hackernews"

    async def _latest_thread_id(self, client: httpx.AsyncClient) -> str | None:
        resp = await client.get(
            _SEARCH_URL,
            params={
                "tags": "story,author_whoishiring",
                "query": "hiring",
                "hitsPerPage": 10,
            },
        )
        resp.raise_for_status()
        hits = resp.json().get("hits", [])
        for h in hits:  # ya vienen ordenados por fecha desc
            if "who is hiring" in (h.get("title") or "").lower():
                return str(h.get("objectID"))
        return None

    async def fetch(self) -> list[ScrapedJob]:
        jobs: list[ScrapedJob] = []
        try:
            async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
                story_id = await self._latest_thread_id(client)
                if not story_id:
                    logger.warning("hackernews: no se encontro hilo 'Who is hiring'")
                    return []

                resp = await client.get(_ITEM_URL.format(story_id=story_id))
                resp.raise_for_status()
                data = resp.json()
        except Exception as exc:  # noqa: BLE001
            logger.warning("hackernews fetch failed: %s", exc)
            return []

        thread_title = data.get("title") or "Who is hiring"

        for child in data.get("children", []):
            raw = child.get("text")
            if not raw or child.get("author") is None:  # borrados
                continue

            text = _strip_html(raw)
            if not text:
                continue
            lines = [ln.strip() for ln in text.split("\n") if ln.strip()]
            if not lines:
                continue

            company, location, role = _parse_header(lines[0])
            if not company or not role:
                continue  # formato libre: no adivinamos

            blob = text.lower()
            if not any(k in blob for k in _TECH_KEYWORDS):
                continue

            is_remote = bool(_REMOTE_RE.search(text)) and not _ONSITE_ONLY_RE.search(text)

            posted_dt = None
            created = child.get("created_at")
            if isinstance(created, str):
                try:
                    posted_dt = datetime.fromisoformat(created.replace("Z", "+00:00"))
                except ValueError:
                    posted_dt = None

            cid = str(child.get("id"))
            jobs.append(
                ScrapedJob(
                    source=self.name,
                    source_id=cid,
                    source_url=f"https://news.ycombinator.com/item?id={cid}",
                    title=role[:200],
                    company=company[:120],
                    location=location or ("Remote" if is_remote else ""),
                    remote=is_remote,
                    posted_at=posted_dt,
                    description=text[:8000],
                    tags=[t for t in _TECH_KEYWORDS if t in blob][:12],
                )
            )

        logger.info("hackernews: hilo=%r ofertas_parseadas=%d", thread_title, len(jobs))
        return self._finalize(jobs)

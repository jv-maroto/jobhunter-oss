"""Scraper Tecnoempleo (ES) - HTML.

Estructura del listado (2026-08): cada oferta es un `div.p-3.border.rounded`
con `h3 a` (titulo + href absoluto), `span.d-block.d-lg-none` con
"<b>Ciudad</b> - dd/mm/aaaa" y badges con las tecnologias. El nombre de la
empresa NO aparece como elemento propio: se deduce del slug de la URL
(`/<titulo>-<empresa>/<tags>/rf-<id>`) quitando la parte del titulo.
"""

from __future__ import annotations

import logging
import re
import unicodedata
from datetime import datetime, timezone

import httpx
from selectolax.parser import HTMLParser

from app.schemas.job import ScrapedJob
from app.scrapers.base import BaseScraper

logger = logging.getLogger(__name__)

# Queries por defecto (solo si el perfil no aporta ninguna).
DEFAULT_QUERIES = ["python", "javascript", "devops", "fullstack", "backend"]
BASE = "https://www.tecnoempleo.com/ofertas-trabajo/{q}"
_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    ),
    "Accept-Language": "es-ES,es;q=0.9,en;q=0.5",
}
_DATE_RE = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
_REMOTE_RE = re.compile(r"remoto|teletrabajo|100\s*%\s*remote|remote", re.IGNORECASE)


def slugify(text: str) -> str:
    s = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    s = re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")
    return s


def query_slug(query: str) -> str:
    """Tecnoempleo enruta por slug: 'ai engineer' -> 'ai-engineer'."""
    return slugify(query) or "python"


def company_from_url(url: str, title: str) -> str:
    """`/senior-python-developer-gcp-appcast/...` con titulo 'Senior Python Developer (GCP)'
    -> 'appcast'. Si no se puede separar, devuelve 'Tecnoempleo'."""
    m = re.search(r"tecnoempleo\.com/([^/]+)/", url)
    if not m:
        return "Tecnoempleo"
    slug = m.group(1)
    title_slug = slugify(title)
    rest = slug
    if title_slug and slug.startswith(title_slug + "-"):
        rest = slug[len(title_slug) + 1 :]
    else:
        # Titulo con palabras reordenadas/quitadas: elimina los tokens del titulo.
        title_tokens = set(title_slug.split("-"))
        rest = "-".join(tok for tok in slug.split("-") if tok not in title_tokens)
    rest = rest.strip("-")
    if not rest:
        return "Tecnoempleo"
    return " ".join(w.capitalize() for w in rest.split("-"))


def parse_listing(html: str, query: str, source_name: str = "tecnoempleo") -> list[ScrapedJob]:
    """Parsea la pagina de resultados y devuelve las ofertas (sin hash)."""
    tree = HTMLParser(html)
    jobs: list[ScrapedJob] = []
    for card in tree.css("div.p-3.border.rounded"):
        link = card.css_first("h3 a[href]")
        if link is None:
            continue
        href = link.attributes.get("href", "").strip()
        title = link.text(strip=True) or link.attributes.get("title", "").strip()
        if not href or not title:
            continue
        if href.startswith("/"):
            href = "https://www.tecnoempleo.com" + href

        location = ""
        posted_at: datetime | None = None
        meta = card.css_first("span.d-block.d-lg-none")
        if meta is not None:
            b = meta.css_first("b")
            if b is not None:
                location = b.text(strip=True)
            dm = _DATE_RE.search(meta.text())
            if dm:
                try:
                    posted_at = datetime(
                        int(dm.group(3)), int(dm.group(2)), int(dm.group(1)), tzinfo=timezone.utc
                    )
                except ValueError:
                    posted_at = None

        tags = [b.text(strip=True) for b in card.css("span.badge") if b.text(strip=True)]
        text = card.text(separator=" ", strip=True)
        remote = bool(_REMOTE_RE.search(location)) or bool(_REMOTE_RE.search(text[:400]))

        jobs.append(
            ScrapedJob(
                source=source_name,
                source_url=href,
                title=title,
                company=company_from_url(href, title),
                location=location or "España",
                remote=remote,
                posted_at=posted_at or datetime.now(tz=timezone.utc),
                description=text[:2000],
                tags=list(dict.fromkeys(tags + [query]))[:12],
            )
        )
    return jobs


class TecnoempleoScraper(BaseScraper):
    name = "tecnoempleo"

    def __init__(self) -> None:
        self.queries: list[str] = list(DEFAULT_QUERIES)

    def configure(
        self,
        *,
        regions: list[str] | None = None,
        queries: list[str] | None = None,
        prefs: dict | None = None,
    ) -> None:
        if queries:
            # Tecnoempleo es solo ES: quita el sufijo "remote" de las variantes.
            cleaned: list[str] = []
            for q in queries:
                q2 = re.sub(r"\b(remote|remoto)\b", "", q, flags=re.IGNORECASE).strip()
                if q2 and q2.lower() not in {c.lower() for c in cleaned}:
                    cleaned.append(q2)
            self.queries = cleaned[:8] or list(DEFAULT_QUERIES)

    async def fetch(self) -> list[ScrapedJob]:
        jobs: list[ScrapedJob] = []
        try:
            async with httpx.AsyncClient(
                timeout=30.0, headers=_HEADERS, follow_redirects=True
            ) as client:
                for q in self.queries:
                    try:
                        resp = await client.get(BASE.format(q=query_slug(q)))
                        if resp.status_code != 200:
                            logger.info("tecnoempleo q=%s -> HTTP %s", q, resp.status_code)
                            continue
                        found = parse_listing(resp.text, q, self.name)
                        if not found:
                            logger.info("tecnoempleo q=%s: 0 tarjetas (¿cambio de HTML?)", q)
                        jobs.extend(found)
                    except Exception as exc:  # noqa: BLE001
                        logger.warning("tecnoempleo q=%s failed: %s", q, exc)
                        continue
        except Exception as exc:  # noqa: BLE001
            logger.warning("tecnoempleo client failed: %s", exc)
            return []

        # Dedup por URL
        seen: set[str] = set()
        uniq: list[ScrapedJob] = []
        for j in jobs:
            if j.source_url in seen:
                continue
            seen.add(j.source_url)
            uniq.append(j)

        return self._finalize(uniq)

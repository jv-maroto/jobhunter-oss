"""Scraper Tecnoempleo - HTML."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

import httpx
from selectolax.parser import HTMLParser

from app.scrapers.base import BaseScraper
from app.schemas.job import ScrapedJob

logger = logging.getLogger(__name__)

QUERIES = [
    "python",
    "fastapi",
    "devops",
    "fullstack",
    "ai-engineer",
]
BASE = "https://www.tecnoempleo.com/ofertas-trabajo/{q}"


class TecnoempleoScraper(BaseScraper):
    name = "tecnoempleo"

    async def fetch(self) -> list[ScrapedJob]:
        jobs: list[ScrapedJob] = []
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
            ),
            "Accept-Language": "es-ES,es;q=0.9,en;q=0.5",
        }
        try:
            async with httpx.AsyncClient(timeout=30.0, headers=headers, follow_redirects=True) as client:
                for q in QUERIES:
                    try:
                        resp = await client.get(BASE.format(q=q))
                        if resp.status_code != 200:
                            continue
                        html = resp.text
                    except Exception as exc:  # noqa: BLE001
                        logger.warning("tecnoempleo q=%s failed: %s", q, exc)
                        continue

                    tree = HTMLParser(html)
                    # Tecnoempleo usa una tarjeta por oferta. Selectores defensivos.
                    cards = tree.css("article, div.p-3.border-bottom")
                    for card in cards:
                        link = card.css_first("a[href*='/ofertas-trabajo/']")
                        if link is None:
                            continue
                        href = link.attributes.get("href", "")
                        if not href:
                            continue
                        if href.startswith("/"):
                            href = "https://www.tecnoempleo.com" + href
                        title = link.text(strip=True)
                        if not title:
                            continue

                        company_el = card.css_first(".text-muted a, .text-primary, span.text-muted")
                        company = company_el.text(strip=True) if company_el else "Unknown"
                        loc_el = card.css_first("[class*='location'], span.fs--14")
                        location = loc_el.text(strip=True) if loc_el else "Spain"
                        remote = "remoto" in (location.lower() + html.lower()[:0])

                        jobs.append(
                            ScrapedJob(
                                source=self.name,
                                source_url=href,
                                title=title,
                                company=company,
                                location=location,
                                remote=remote,
                                posted_at=datetime.now(tz=timezone.utc),
                                description=card.text(strip=True)[:2000],
                                tags=[q],
                            )
                        )
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

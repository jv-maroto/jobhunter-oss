"""Scraper We Work Remotely via sus feeds RSS publicos (ToS bajo).

Solo se activa para la pseudo-region REMOTE (lo decide el registry/catalogo).
Los items RSS traen el titulo en formato "Empresa: Puesto".
"""

from __future__ import annotations

import logging
from email.utils import parsedate_to_datetime
from xml.etree import ElementTree as ET

import httpx

from app.schemas.job import ScrapedJob
from app.scrapers.base import BaseScraper

logger = logging.getLogger(__name__)

FEEDS = [
    "https://weworkremotely.com/categories/remote-programming-jobs.rss",
    "https://weworkremotely.com/categories/remote-devops-sysadmin-jobs.rss",
    "https://weworkremotely.com/categories/remote-full-stack-programming-jobs.rss",
]


def _strip_html(text: str) -> str:
    out: list[str] = []
    depth = 0
    for ch in text:
        if ch == "<":
            depth += 1
        elif ch == ">":
            depth = max(0, depth - 1)
        elif depth == 0:
            out.append(ch)
    return "".join(out).strip()


class WeWorkRemotelyScraper(BaseScraper):
    name = "weworkremotely"

    async def fetch(self) -> list[ScrapedJob]:
        jobs: list[ScrapedJob] = []
        seen: set[str] = set()
        headers = {"User-Agent": "jobhunter", "Accept": "application/rss+xml, application/xml"}
        try:
            async with httpx.AsyncClient(timeout=30.0, headers=headers, follow_redirects=True) as client:
                for feed in FEEDS:
                    try:
                        resp = await client.get(feed)
                        resp.raise_for_status()
                        root = ET.fromstring(resp.text)
                    except Exception as exc:  # noqa: BLE001
                        logger.warning("wwr feed=%s failed: %s", feed, exc)
                        continue

                    for item in root.iter("item"):
                        link = (item.findtext("link") or "").strip()
                        if not link or link in seen:
                            continue
                        seen.add(link)

                        raw_title = (item.findtext("title") or "").strip()
                        if ":" in raw_title:
                            company, title = raw_title.split(":", 1)
                            company, title = company.strip(), title.strip()
                        else:
                            company, title = "Unknown", raw_title
                        if not title:
                            continue

                        pub = item.findtext("pubDate")
                        try:
                            posted_dt = parsedate_to_datetime(pub) if pub else None
                        except Exception:  # noqa: BLE001
                            posted_dt = None

                        region = (item.findtext("region") or "").strip()
                        desc = _strip_html(item.findtext("description") or "")[:8000]

                        jobs.append(
                            ScrapedJob(
                                source=self.name,
                                source_url=link,
                                title=title,
                                company=company,
                                location=region or "Remote",
                                remote=True,
                                posted_at=posted_dt,
                                description=desc,
                                tags=["remote"],
                            )
                        )
        except Exception as exc:  # noqa: BLE001
            logger.warning("wwr client failed: %s", exc)
            return []

        return self._finalize(jobs)

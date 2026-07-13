"""Fetch a short summary of a linked article (og:description or meta description).

Used to enrich trending posts with a real preview from the source page.
"""

from __future__ import annotations

import asyncio
import ipaddress
import logging
import re
import socket
from html import unescape
from typing import Iterable
from urllib.parse import urlsplit

import httpx

logger = logging.getLogger(__name__)


def _is_safe_public_url(url: str) -> bool:
    """SSRF guard: solo http(s) hacia hosts que resuelven a IPs públicas.

    Las URLs vienen de historias de Hacker News (cualquiera puede publicarlas),
    así que sin este filtro un atacante podría apuntar el fetch del servidor a
    localhost / la red interna / metadata de cloud.
    """
    try:
        parts = urlsplit(url)
    except ValueError:
        return False
    if parts.scheme not in ("http", "https"):
        return False
    host = parts.hostname
    if not host:
        return False
    try:
        infos = socket.getaddrinfo(host, parts.port or (443 if parts.scheme == "https" else 80))
    except OSError:
        return False
    for info in infos:
        ip_str = info[4][0]
        try:
            ip = ipaddress.ip_address(ip_str)
        except ValueError:
            return False
        if (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_reserved
            or ip.is_multicast
            or ip.is_unspecified
        ):
            return False
    return True


# Browser-like headers — some sites 403 the default httpx UA
_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml",
    "Accept-Language": "en-US,en;q=0.9,es;q=0.8",
}

_META_OG = re.compile(
    r'<meta[^>]+(?:property|name)\s*=\s*"og:description"[^>]*\bcontent\s*=\s*"([^"]+)"',
    re.IGNORECASE,
)
_META_TW = re.compile(
    r'<meta[^>]+(?:name|property)\s*=\s*"twitter:description"[^>]*\bcontent\s*=\s*"([^"]+)"',
    re.IGNORECASE,
)
_META_DESC = re.compile(
    r'<meta[^>]+name\s*=\s*"description"[^>]*\bcontent\s*=\s*"([^"]+)"',
    re.IGNORECASE,
)
_META_OG_REVERSED = re.compile(
    r'<meta[^>]+content\s*=\s*"([^"]+)"[^>]*(?:property|name)\s*=\s*"og:description"',
    re.IGNORECASE,
)


def _clean(text: str, max_len: int = 280) -> str:
    text = unescape(text)
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) > max_len:
        text = text[: max_len - 1].rsplit(" ", 1)[0] + "…"
    return text


def _extract(html: str) -> str | None:
    # Only scan the <head> to avoid catching body content
    head_end = html.lower().find("</head>")
    chunk = html[: head_end if head_end != -1 else 50_000]
    for rx in (_META_OG, _META_OG_REVERSED, _META_TW, _META_DESC):
        m = rx.search(chunk)
        if m:
            return _clean(m.group(1))
    return None


async def fetch_one(client: httpx.AsyncClient, url: str) -> str:
    """Returns summary or empty string.

    Follows redirects manually (max 3 hops) revalidando cada URL contra el
    guard SSRF, ya que un host público podría redirigir a uno interno.
    """
    try:
        current = url
        for _ in range(4):
            if not _is_safe_public_url(current):
                logger.debug("article summary skipped unsafe url: %s", current)
                return ""
            r = await client.get(
                current, headers=_HEADERS, follow_redirects=False, timeout=10.0
            )
            if r.is_redirect:
                location = r.headers.get("location")
                if not location:
                    return ""
                current = str(r.url.join(location))
                continue
            if r.status_code != 200:
                return ""
            ctype = r.headers.get("content-type", "")
            if "html" not in ctype.lower():
                return ""
            return _extract(r.text) or ""
        return ""
    except Exception as exc:  # noqa: BLE001
        logger.debug("article summary fetch failed for %s: %s", url, exc)
        return ""


async def fetch_summaries(urls: Iterable[str]) -> dict[str, str]:
    """Parallel fetch — returns {url: summary} (empty string on failure)."""
    urls_list = [u for u in urls if u]
    if not urls_list:
        return {}
    async with httpx.AsyncClient() as client:
        results = await asyncio.gather(
            *(fetch_one(client, u) for u in urls_list), return_exceptions=True
        )
    out: dict[str, str] = {}
    for url, res in zip(urls_list, results, strict=False):
        out[url] = res if isinstance(res, str) else ""
    return out

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

# og:image / twitter:image extractors — used for the AMD-style banner hero.
_META_OGIMG = re.compile(
    r'<meta[^>]+(?:property|name)\s*=\s*"og:image(?::secure_url)?"[^>]*\bcontent\s*=\s*"([^"]+)"',
    re.IGNORECASE,
)
_META_OGIMG_REVERSED = re.compile(
    r'<meta[^>]+content\s*=\s*"([^"]+)"[^>]*(?:property|name)\s*=\s*"og:image(?::secure_url)?"',
    re.IGNORECASE,
)
_META_TWIMG = re.compile(
    r'<meta[^>]+(?:name|property)\s*=\s*"twitter:image(?::src)?"[^>]*\bcontent\s*=\s*"([^"]+)"',
    re.IGNORECASE,
)


def _clean(text: str, max_len: int = 280) -> str:
    text = unescape(text)
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) > max_len:
        text = text[: max_len - 1].rsplit(" ", 1)[0] + "…"
    return text


def _extract(html: str) -> str | None:
    head_end = html.lower().find("</head>")
    chunk = html[: head_end if head_end != -1 else 50_000]
    for rx in (_META_OG, _META_OG_REVERSED, _META_TW, _META_DESC):
        m = rx.search(chunk)
        if m:
            return _clean(m.group(1))
    return None


def _extract_image(html: str, base_url: str = "") -> str | None:
    """Extract og:image URL (absolute) or None."""
    head_end = html.lower().find("</head>")
    chunk = html[: head_end if head_end != -1 else 50_000]
    for rx in (_META_OGIMG, _META_OGIMG_REVERSED, _META_TWIMG):
        m = rx.search(chunk)
        if m:
            url = unescape(m.group(1)).strip()
            if url.startswith("//"):
                url = "https:" + url
            elif url.startswith("/") and base_url:
                m2 = re.match(r"(https?://[^/]+)", base_url)
                if m2:
                    url = m2.group(1) + url
            if url.startswith("http"):
                return url
    return None


async def fetch_one(client: httpx.AsyncClient, url: str) -> dict[str, str]:
    """Returns {summary, image}. Both empty strings on failure.

    Follows redirects manually revalidando cada URL contra el guard SSRF.
    """
    try:
        current = url
        for _ in range(4):
            if not _is_safe_public_url(current):
                logger.debug("article fetch skipped unsafe url: %s", current)
                return {"summary": "", "image": ""}
            r = await client.get(
                current, headers=_HEADERS, follow_redirects=False, timeout=10.0
            )
            if r.is_redirect:
                location = r.headers.get("location")
                if not location:
                    return {"summary": "", "image": ""}
                current = str(r.url.join(location))
                continue
            if r.status_code != 200:
                return {"summary": "", "image": ""}
            ctype = r.headers.get("content-type", "")
            if "html" not in ctype.lower():
                return {"summary": "", "image": ""}
            return {
                "summary": _extract(r.text) or "",
                "image": _extract_image(r.text, str(r.url)) or "",
            }
        return {"summary": "", "image": ""}
    except Exception as exc:  # noqa: BLE001
        logger.debug("article fetch failed for %s: %s", url, exc)
        return {"summary": "", "image": ""}


async def fetch_metas(urls: Iterable[str]) -> dict[str, dict[str, str]]:
    """Parallel fetch — returns {url: {summary, image}}."""
    urls_list = [u for u in urls if u]
    if not urls_list:
        return {}
    async with httpx.AsyncClient() as client:
        results = await asyncio.gather(
            *(fetch_one(client, u) for u in urls_list), return_exceptions=True
        )
    out: dict[str, dict[str, str]] = {}
    for url, res in zip(urls_list, results, strict=False):
        out[url] = res if isinstance(res, dict) else {"summary": "", "image": ""}
    return out


async def fetch_summaries(urls: Iterable[str]) -> dict[str, str]:
    """Parallel fetch — returns {url: summary}. Legacy shim over fetch_metas()."""
    metas = await fetch_metas(urls)
    return {u: m.get("summary", "") for u, m in metas.items()}

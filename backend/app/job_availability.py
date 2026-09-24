"""Evidence-based availability checks, separate from listing age/ranking.

All network reads reuse the pinned HTTPS public-source reader. A successful
HTTP response alone never establishes that applications remain open.
"""
from __future__ import annotations

import asyncio
import json
import re
import threading
from datetime import datetime, timedelta, timezone
from typing import Any

from selectolax.parser import HTMLParser

from app.career.sources import fetch_public_document
from app.job_freshness import parse_posted_at
from app.schemas.job import canonical_job_url

_NETWORK_SLOTS = threading.BoundedSemaphore(2)
_CLOSED = re.compile(
    r"\b(?:no longer accepting applications|no longer available|this (?:job(?: posting)?|position|vacancy) (?:has expired|is closed|has been filled)|"
    r"ya no se aceptan solicitudes|ya no acepta solicitudes|esta oferta(?: de empleo)? (?:ha caducado|ya no está disponible)|puesto (?:cerrado|cubierto))\b",
    re.I,
)


def result(status: str, reason: str, evidence: str, expires_at: str | None = None) -> dict:
    return {"status": status, "checked_at": datetime.now(timezone.utc).isoformat(),
            "reason": reason, "evidence": evidence, "expires_at": expires_at}


def expiration(value: Any) -> datetime | None:
    parsed = parse_posted_at(value)
    # A date-only deadline is inclusive of the stated day, not its first second.
    if parsed and isinstance(value, str) and re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        parsed += timedelta(days=1)
    return parsed


def effective_availability(value: dict | None) -> dict | None:
    """Age previously stored evidence without changing when it was checked."""
    if value is None:
        return None
    current = dict(value)
    deadline = expiration(current.get("expires_at") or current.get("validThrough"))
    now = datetime.now(timezone.utc)
    if deadline and deadline <= now:
        current.update(status="expired", reason="La fecha límite declarada ya pasó",
                       evidence="explicit_deadline", expires_at=deadline.isoformat())
    elif current.get("status") == "active":
        checked = parse_posted_at(current.get("checked_at"))
        if checked is None or checked > now or now - checked > timedelta(hours=24):
            current.update(status="unverified", reason="La comprobación es antigua o no tiene una fecha válida; vuelve a verificar",
                           evidence="stale_verification")
    return current


def _closed(text: str) -> bool:
    for sentence in re.split(r"[.!?\n]+", text):
        for match in _CLOSED.finditer(sentence):
            prefix = sentence[max(0, match.start() - 100):match.start()]
            if not re.search(r"\b(?:if|when|once|whether|in case|si|cuando|en caso de)\b", prefix, re.I):
                return True
    return False


def assess_listing(job: dict, *, ats_present: bool = False) -> dict:
    deadline = expiration(job.get("valid_through") or job.get("validThrough") or job.get("expires_at"))
    if deadline and deadline < datetime.now(timezone.utc):
        return result("expired", "La fecha límite declarada ya pasó", "explicit_deadline", deadline.isoformat())
    text = str(job.get("description") or "")
    if _closed(text):
        return result("expired", "El anuncio indica que está cerrado o caducado", "explicit_closed_text")
    if ats_present:
        return result("active", "La oferta figura en el listado público actual de la empresa", "current_ats_listing", deadline.isoformat() if deadline else None)
    return result("unverified", "La antigüedad o la presencia en un buscador no confirman que siga abierta", "insufficient_evidence", deadline.isoformat() if deadline else None)


def _norm(value):
    return " ".join(re.findall(r"\w+", str(value or "").casefold()))


def _postings(value):
    if isinstance(value, list):
        for item in value:
            yield from _postings(item)
    elif isinstance(value, dict):
        types = value.get("@type") or []
        if types == "JobPosting" or (isinstance(types, list) and "JobPosting" in types):
            yield value
        for key in ("@graph", "mainEntity", "itemListElement", "item"):
            if key in value:
                yield from _postings(value[key])


def assess_document(job: dict, html: str, final_url: str = "") -> dict:
    document = HTMLParser(html)
    postings = []
    for script in document.css('script[type="application/ld+json"]'):
        try:
            postings.extend(_postings(json.loads(script.text())))
        except (ValueError, TypeError, RecursionError):
            continue
    for node in document.css("script,style,noscript,nav,footer"):
        node.decompose()
    visible = document.text(separator=" ", strip=True)
    if _closed(visible):
        return result("expired", "La página indica que la oferta ya no acepta candidaturas", "page_closed_text")
    title = _norm(job.get("title"))
    def same_posting(posting):
        if not title or _norm(posting.get("title")) != title:
            return False
        organization = posting.get("hiringOrganization")
        if isinstance(organization, dict) and organization.get("name") and job.get("company"):
            if _norm(organization["name"]) != _norm(job["company"]):
                return False
        if posting.get("url"):
            if not isinstance(posting["url"], str):
                return False
            candidates = [url for url in (final_url, job.get("source_url"), job.get("url")) if url]
            try:
                if candidates and canonical_job_url(posting["url"]) not in {canonical_job_url(url) for url in candidates}:
                    return False
            except (ValueError, TypeError):
                return False
        return True
    matching = [posting for posting in postings if same_posting(posting)]
    if len(matching) != 1:
        return result("unverified", "La página no aporta un anuncio y una fecha límite inequívocos", "no_matching_jobposting")
    posting = matching[0]
    deadline = expiration(posting.get("validThrough"))
    if deadline:
        if deadline < datetime.now(timezone.utc):
            return result("expired", "La fecha límite publicada ya pasó", "jobposting_validThrough", deadline.isoformat())
        return result("active", "El anuncio coincidente publica una fecha límite futura", "jobposting_validThrough", deadline.isoformat())
    return result("unverified", "El anuncio existe, pero no confirma un plazo de candidatura vigente", "jobposting_without_deadline")


def _fetch_guarded(url):
    try:
        return fetch_public_document(url)
    finally:
        _NETWORK_SLOTS.release()


async def check_listing(job: dict) -> dict:
    local = assess_listing(job)
    if local["status"] == "expired":
        return local
    url = job.get("source_url") or job.get("url")
    if not isinstance(url, str) or not url:
        return result("unverified", "Falta una URL pública para comprobar la oferta", "missing_url")
    if not _NETWORK_SLOTS.acquire(blocking=False):
        return result("unverified", "Comprobaciones ocupadas; se puede reintentar", "verification_busy")
    # The slot is released by the worker, including after an async timeout, so
    # repeated requests cannot spawn unlimited live network checks.
    task = asyncio.create_task(asyncio.to_thread(_fetch_guarded, url))
    try:
        html, content_type, final_url = await asyncio.wait_for(asyncio.shield(task), timeout=20)
    except TimeoutError:
        task.add_done_callback(_consume_exception)
        return result("unverified", "La página no respondió dentro del límite", "timeout")
    except asyncio.CancelledError:
        task.add_done_callback(_consume_exception)
        raise
    except ValueError as exc:
        if re.fullmatch(r"Fuente no disponible \(HTTP (404|410)\)", str(exc)):
            return result("expired", "La URL devuelve que el anuncio no existe o fue retirado", "http_404_or_410")
        return result("unverified", "No se pudo comprobar la página de forma segura", "unreadable_page")
    except Exception:
        return result("unverified", "No se pudo acceder al anuncio", "network_error")
    if "html" not in content_type.lower():
        return result("unverified", "La URL no devuelve una página de anuncio HTML", "unsupported_document")
    return assess_document(job, html, final_url)


def _consume_exception(task):
    if not task.cancelled():
        task.exception()


async def verify_scraped_jobs(jobs: list, *, max_checks: int = 8, ats_present: bool = False) -> list[tuple[Any, dict]]:
    """Assess every job, network-check at most 8; never silently discard unknowns."""
    semaphore = asyncio.Semaphore(2)
    async def verify(index, job):
        data = job.model_dump() if hasattr(job, "model_dump") else dict(job)
        local = assess_listing(data, ats_present=ats_present)
        if local["status"] != "unverified" or index >= min(8, max(0, max_checks)):
            return job, local
        async with semaphore:
            return job, await check_listing(data)
    return await asyncio.gather(*(verify(index, job) for index, job in enumerate(jobs)))


def needs_indeed_verification(job) -> bool:
    """Indeed listings must have fresh positive evidence before discovery display."""
    from urllib.parse import urlsplit

    try:
        host = (urlsplit(getattr(job, "source_url", "") or "").hostname or "").lower()
    except ValueError:
        host = ""
    indeed = (getattr(job, "source", "") or "").lower() == "indeed" or bool(re.search(r"(^|\.)indeed\.(com|[a-z]{2}|co\.[a-z]{2}|com\.[a-z]{2})$", host))
    return indeed and (effective_availability(getattr(job, "availability", None)) or {}).get("status") != "active"

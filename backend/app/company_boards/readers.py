"""Bounded public ATS board readers; no arbitrary URL fetching or applications.

Contracts verified against official docs (2026-09-22):
https://docs.greenhouse.io/job-board.html
https://github.com/lever/postings-api
https://developers.ashbyhq.com/docs/public-job-posting-api
"""
from __future__ import annotations

import asyncio
import json
import math
import re
from html import unescape
from typing import Any

import httpx
from selectolax.parser import HTMLParser

from app.schemas.job import JobImport

MAX_BYTES = 8_000_000
MAX_JOBS = 200
MAX_DESCRIPTION = 100_000
PROVIDERS = {"greenhouse", "lever", "lever_eu", "ashby"}


def validate_slug(slug: str) -> str:
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,99}", slug):
        raise ValueError("Use the board slug only: letters, digits, hyphen or underscore (100 characters maximum)")
    return slug


def endpoint(provider: str, slug: str) -> tuple[str, dict]:
    validate_slug(slug)
    if provider == "greenhouse":
        return f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs", {"content": "true"}
    if provider in {"lever", "lever_eu"}:
        host = "api.eu.lever.co" if provider == "lever_eu" else "api.lever.co"
        return f"https://{host}/v0/postings/{slug}", {"mode": "json", "limit": MAX_JOBS + 1}
    if provider == "ashby":
        return f"https://api.ashbyhq.com/posting-api/job-board/{slug}", {"includeCompensation": "true"}
    raise ValueError("Unsupported board provider")


def plain(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    document = HTMLParser(unescape(value))
    for node in document.css("script,style,noscript"):
        node.decompose()
    return document.text(separator="\n", strip=True)


def number(value):
    if isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) and value >= 0:
        return value
    return None


def compensation(row: dict, provider: str) -> dict:
    raw = row.get("salaryRange") if provider.startswith("lever") else row.get("compensation")
    value = raw if isinstance(raw, dict) else {}
    if provider == "ashby":
        components = value.get("summaryComponents") or []
        salaries = [item for item in components if isinstance(item, dict) and item.get("compensationType") == "Salary"]
        value = salaries[0] if len(salaries) == 1 else {}
    interval = str(value.get("interval") or "").lower()
    period = {"year": "year", "yearly": "year", "annually": "year", "per-year-salary": "year", "1 year": "year", "month": "month", "monthly": "month", "1 month": "month", "week": "week", "weekly": "week", "1 week": "week", "hour": "hour", "hourly": "hour", "1 hour": "hour", "day": "day", "daily": "day", "1 day": "day"}.get(interval)
    return {"salary_min": number(value.get("min", value.get("minValue"))),
            "salary_max": number(value.get("max", value.get("maxValue"))),
            "currency": value.get("currency", value.get("currencyCode")),
            "salary_period": period, "compensation_raw": raw}


def parse_jobs(provider: str, payload: Any, company: str) -> dict:
    rows = payload if provider.startswith("lever") else payload.get("jobs") if isinstance(payload, dict) else None
    if not isinstance(rows, list):
        raise ValueError("Unexpected ATS response schema")
    jobs, skipped = [], 0
    for row in rows[:MAX_JOBS]:
        if not isinstance(row, dict):
            skipped += 1
            continue
        if provider == "ashby" and row.get("isListed") is False:
            continue
        if provider == "greenhouse":
            title, url = row.get("title"), row.get("absolute_url")
            location = row.get("location") or {}
            location = location.get("name", "") if isinstance(location, dict) else ""
            description, remote = plain(row.get("content")), None
        elif provider.startswith("lever"):
            title, url = row.get("text"), row.get("hostedUrl")
            categories = row.get("categories") or {}
            location = categories.get("location", "") if isinstance(categories, dict) else ""
            chunks = [row.get("descriptionPlain") or plain(row.get("description"))]
            for part in row.get("lists") or []:
                if isinstance(part, dict):
                    chunks += [part.get("text"), plain(part.get("content"))]
            chunks += [row.get("additionalPlain") or plain(row.get("additional")), row.get("salaryDescriptionPlain") or plain(row.get("salaryDescription"))]
            description = "\n\n".join(str(chunk) for chunk in chunks if chunk)
            remote = {"remote": True, "on-site": False, "hybrid": False}.get(row.get("workplaceType"))
        else:
            title, url = row.get("title"), row.get("jobUrl")
            location = row.get("location") or ""
            description = row.get("descriptionPlain") or plain(row.get("descriptionHtml"))
            remote = row.get("isRemote") if isinstance(row.get("isRemote"), bool) else None
        try:
            url = JobImport.public_job_url(url)
        except ValueError:
            url = None
        if not isinstance(title, str) or not title.strip() or not url or not isinstance(description, str):
            skipped += 1
            continue
        jobs.append({"source_id": str(row.get("id") or url), "title": title[:512],
                     "company": company, "location": str(location)[:256], "remote": remote,
                     "description": description[:MAX_DESCRIPTION], "url": url,
                     "description_truncated": len(description) > MAX_DESCRIPTION,
                     "posted_at": row.get("publishedAt"), **compensation(row, provider)})
    return {"jobs": jobs, "received": len(rows), "skipped": skipped,
            "truncated": len(rows) > MAX_JOBS,
            "note": "Company-specific public board, not a worldwide vacancy index. Location and remote eligibility remain unverified."}


async def fetch_board(provider: str, slug: str, company: str, *, transport=None) -> dict:
    url, params = endpoint(provider, slug)
    async with asyncio.timeout(45):
        async with httpx.AsyncClient(timeout=20, follow_redirects=False, transport=transport, trust_env=False) as client:
            async with client.stream("GET", url, params=params, headers={"Accept": "application/json"}) as response:
                response.raise_for_status()
                content = bytearray()
                async for chunk in response.aiter_bytes():
                    content.extend(chunk)
                    if len(content) > MAX_BYTES:
                        raise ValueError("Board exceeds response size limit; previous results preserved")
    return parse_jobs(provider, json.loads(content), company)

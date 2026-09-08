"""Shared rate limiter instance.

Kept in its own module so `app.main` can register it against the FastAPI app
AND individual routers can decorate their heavy endpoints without creating an
`app.main <-> app.api.*` import cycle.

In-memory storage is the right call for a single-user local backend; if you
ever multi-tenant this, swap to Redis by passing `storage_uri="redis://..."`.
"""

from __future__ import annotations

from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(
    key_func=get_remote_address,
    # Generous default — the dashboard fires 15+ image thumbnail requests per
    # /linkedin render, plus polling every 30s from useBackendHealth /
    # useScrapeStatus. Under 120/min the default was starving the UI in
    # React StrictMode. Individual expensive endpoints override with tighter
    # per-endpoint decorators (scrape, prepare-application, generate-*).
    default_limits=["600/minute"],
    headers_enabled=True,
)

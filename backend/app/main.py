"""FastAPI app entrypoint."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import (
    comments,
    ext,
    jobs,
    metrics,
    onboarding,
    persons,
    posts,
    search_profile,
    settings as settings_api,
)
from app.config import settings
from app.db import init_db
from app.scheduler import start_scheduler, stop_scheduler

logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    logger.info("startup: init_db()")
    init_db()
    settings.data_path  # asegura dirs

    # Inicializar router LLM (multi-provider con fallback)
    try:
        from app.ai.cost_tracker import get_cost_tracker
        from app.ai.router import build_default_router, set_router

        tracker = get_cost_tracker()
        router = build_default_router(cost_tracker=tracker)
        set_router(router)
        available = {
            tier: router.available_providers(tier)
            for tier in ("scoring", "generation", "messaging")
        }
        logger.info("LLM router inicializado. Providers disponibles por tier: %s", available)
    except Exception as exc:  # noqa: BLE001
        logger.warning("No se pudo inicializar LLM router: %s", exc)

    start_scheduler()
    try:
        yield
    finally:
        logger.info("shutdown: stopping scheduler")
        stop_scheduler()


app = FastAPI(
    title="Jobhunter Backend",
    version="0.1.0",
    description="Automated job search system: scraping, scoring with Claude Haiku, CV/cover generation with Claude Sonnet.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_origin_regex=r"chrome-extension://.*",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(jobs.router)
app.include_router(persons.router)
app.include_router(posts.router)
app.include_router(metrics.router)
app.include_router(ext.router)
app.include_router(comments.router)
app.include_router(settings_api.router)
app.include_router(onboarding.router)
app.include_router(search_profile.router)


@app.get("/")
def root() -> dict:
    return {
        "name": "jobhunter-backend",
        "version": "0.1.0",
        "docs": "/docs",
        "endpoints": [
            "/jobs",
            "/persons",
            "/posts",
            "/metrics/today",
            "/metrics/pipeline",
            "/metrics/companies",
            "/ext/tasks",
        ],
    }


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}

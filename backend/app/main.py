"""FastAPI app entrypoint."""

from __future__ import annotations

import logging
import shutil
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import (
    ai_settings,
    apply,
    comments,
    ext,
    integrations,
    jobs,
    metrics,
    networking,
    onboarding,
    persons,
    posts,
    search_profile,
)
from app.api import (
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


def bootstrap_cv_master() -> None:
    """En un clon recien hecho no existe `cv_master.json` (esta gitignoreado a
    proposito: es tu perfil, no debe versionarse). Lo creamos a partir de
    `cv_master.example.json`, que si viene en el repo.

    La plantilla lleva `_README`, que es la señal que usa `detect.is_onboarded()`
    para saber que la instancia esta sin configurar -> se lanza el wizard.
    """
    target = settings.cv_master_file
    if target.exists():
        return
    example = target.with_name("cv_master.example.json")
    if not example.exists():
        logger.warning("no hay cv_master.json ni cv_master.example.json en %s", target.parent)
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(example, target)
    logger.info("primer arranque: cv_master.json creado desde la plantilla. Completa el onboarding.")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    logger.info("startup: init_db()")
    init_db()
    settings.data_path  # asegura dirs
    bootstrap_cv_master()

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
    description=(
        "Self-hosted job search: scraping, LLM scoring (Anthropic / OpenAI / Gemini / "
        "Ollama), tailored CV + cover letter generation."
    ),
    lifespan=lifespan,
)

if settings.cors_extension_regex is None:
    logger.info("CORS: extensión Chrome restringida a chrome_extension_id configurado")
else:
    logger.warning(
        "CORS: se permite cualquier chrome-extension:// (fija CHROME_EXTENSION_ID "
        "en .env para restringir a tu extensión)"
    )

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_origin_regex=settings.cors_extension_regex,
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
app.include_router(integrations.router)
app.include_router(apply.router)
app.include_router(ai_settings.router)
app.include_router(networking.router)


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
    """Basic liveness + capability probe.

    Reports whether external binaries required for CV generation are actually
    installed. Frontend can surface a warning if typst is missing — that's
    what breaks 'Prepare application' with the 'file missing on disk' errors.
    """
    import shutil as _sh
    typst_ok = _sh.which("typst") is not None
    return {
        "status": "ok",
        "capabilities": {"typst": typst_ok},
        "warnings": (
            []
            if typst_ok
            else [
                "typst binary not installed — 'Prepare application' will fail. "
                "Install with `brew install typst` (macOS), "
                "`winget install typst` (Windows), "
                "or run the project with `docker compose up`."
            ]
        ),
    }

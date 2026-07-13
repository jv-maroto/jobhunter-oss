"""Endpoints del perfil de busqueda y catalogo de plataformas (Pilar 2).

Permiten al usuario elegir paises/plataformas y derivar las queries, sin tocar
el JSON a mano. Escriben en cv_master.json::search_preferences (con backup +
invalidacion de cache, mismo patron que settings.put_cv_master). Local-first.
"""

from __future__ import annotations

import json
import logging
import shutil
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_db
from app.scrapers.country_map import resolve_regions
from app.scrapers.query_builder import build_search_queries
from app.scrapers.registry import active_platforms, load_catalog, suggest_platforms
from app.schemas.search import PlatformInfo, SearchProfileIn, SearchProfileOut

logger = logging.getLogger(__name__)
router = APIRouter(tags=["search-profile"])


def _load_cv() -> dict[str, Any]:
    path = settings.cv_master_file
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return {}


def _write_cv(cv: dict[str, Any]) -> None:
    path = settings.cv_master_file
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        backups = path.parent / "cv_master_backups"
        backups.mkdir(exist_ok=True)
        ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        shutil.copy2(path, backups / f"cv_master_{ts}.json")
    path.write_text(json.dumps(cv, ensure_ascii=False, indent=2), encoding="utf-8")
    try:
        from app.services import load_cv_master

        load_cv_master.cache_clear()
    except Exception:  # noqa: BLE001
        pass


def _platform_info(p: dict) -> PlatformInfo:
    return PlatformInfo(
        id=p["id"],
        label=p.get("label", p["id"]),
        method=p.get("method", ""),
        countries=p.get("countries", []),
        apply_support=p.get("apply_support", ""),
        tos_risk=p.get("tos_risk", ""),
        enabled_by_default=bool(p.get("enabled_by_default")),
        # Sin esto la UI pintaba un toggle verde para plataformas que no existen:
        # el usuario las activaba y no se buscaba nada, sin aviso.
        implemented=bool(p.get("implemented")),
        status=p.get("status", "available"),
        requires_env=p.get("requires_env"),
        notes=p.get("notes"),
    )


def _build_out(cv: dict) -> SearchProfileOut:
    prefs = cv.get("search_preferences", {}) or {}
    regions = resolve_regions(prefs)
    return SearchProfileOut(
        search_preferences=prefs,
        regions=regions,
        queries_preview=build_search_queries(cv, prefs),
        active_platforms=[_platform_info(p) for p in active_platforms(prefs, regions)],
        suggested_platforms=[_platform_info(p) for p in suggest_platforms(regions)],
    )


@router.get("/settings/search-profile", response_model=SearchProfileOut)
def get_search_profile() -> SearchProfileOut:
    return _build_out(_load_cv())


@router.put("/settings/search-profile", response_model=SearchProfileOut)
def put_search_profile(body: SearchProfileIn) -> SearchProfileOut:
    cv = _load_cv()
    prefs = dict(cv.get("search_preferences", {}) or {})
    # Solo aplica los campos provistos (no None), incluidos los extra permitidos.
    patch = body.model_dump(exclude_none=True)
    prefs.update(patch)
    cv["search_preferences"] = prefs
    _write_cv(cv)
    return _build_out(cv)


@router.get("/settings/platforms/catalog")
def get_catalog() -> dict[str, Any]:
    return {"platforms": load_catalog()}


@router.get("/settings/platforms/suggested")
def get_suggested(regions: str = Query("", description="ISO coma-separado, p.ej. ES,SE")) -> dict:
    reg = [r.strip().upper() for r in regions.split(",") if r.strip()]
    # Acepta presets/EU/REMOTE igual que el perfil.
    resolved = resolve_regions({"regions": reg}) if reg else []
    return {"platforms": [_platform_info(p).model_dump() for p in suggest_platforms(resolved)]}


@router.post("/scrape/run")
async def run_scrape_now(db: Session = Depends(get_db)) -> dict[str, int]:
    """Lanza un ciclo de scraping+ingest con la configuracion actual ('Buscar ahora')."""
    from app.services import scrape_and_ingest

    return await scrape_and_ingest(db)

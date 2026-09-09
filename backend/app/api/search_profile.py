"""Endpoints del perfil de busqueda y catalogo de plataformas (Pilar 2).

Permiten al usuario elegir paises/plataformas y derivar las queries, sin tocar
el JSON a mano. Escriben en cv_master.json::search_preferences (con backup +
invalidacion de cache, mismo patron que settings.put_cv_master). Local-first.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db import get_db
from app.profile_store import read_profile, write_profile
from app.schemas.search import PlatformInfo, SearchProfileIn, SearchProfileOut
from app.scrapers.country_map import resolve_regions
from app.scrapers.query_builder import build_search_queries
from app.scrapers.registry import active_platforms, load_catalog, suggest_platforms

logger = logging.getLogger(__name__)
router = APIRouter(tags=["search-profile"])


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
    return _build_out(read_profile())


@router.put("/settings/search-profile", response_model=SearchProfileOut)
def put_search_profile(body: SearchProfileIn) -> SearchProfileOut:
    cv = read_profile()
    prefs = dict(cv.get("search_preferences", {}) or {})
    patch = body.model_dump(exclude_unset=True)
    if "region_preset" in patch and "regions" not in patch:
        prefs.pop("regions", None)
    prefs.update(patch)
    try:
        SearchProfileIn.model_validate(prefs)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="Invalid merged search preferences") from exc
    cv["search_preferences"] = prefs
    write_profile(cv)
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
async def run_scrape_now(db: Session = Depends(get_db)) -> dict[str, Any]:
    """Lanza un ciclo de scraping+ingest con la configuracion actual ('Buscar ahora')."""
    from app.onboarding.detect import is_onboarded
    from app.services import scrape_and_ingest

    if not is_onboarded():
        raise HTTPException(
            status_code=409,
            detail="Completa el onboarding antes de buscar ofertas (sin perfil no hay queries).",
        )
    return await scrape_and_ingest(db)

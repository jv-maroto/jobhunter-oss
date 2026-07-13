"""Registry / factory de scrapers dirigido por las preferencias del usuario.

Punto UNICO de inyeccion del scraping (lo consume `services.run_all_scrapers`).
Combina el catalogo estatico (`platforms.json`) con las preferencias del
usuario (`cv_master.json::search_preferences`) para construir las instancias de
scraper ya configuradas.

RETROCOMPATIBLE: si las preferencias no traen configuracion dinamica explicita
(`regions`/`region_preset`/`platforms`/`queries`) — el caso del template recien
clonado — se devuelve EXACTAMENTE el conjunto legacy `ALL_SCRAPERS`, de modo que
una instalacion sin configurar se comporta igual que antes de este refactor.
"""

from __future__ import annotations

import json
import logging
from functools import lru_cache

from app.config import settings
from app.scrapers.adzuna import AdzunaScraper
from app.scrapers.arbeitnow import ArbeitnowScraper
from app.scrapers.base import BaseScraper
from app.scrapers.country_map import EU_COUNTRIES, jobspy_params_for, resolve_regions
from app.scrapers.hackernews_jobs import HackerNewsWhoIsHiringScraper
from app.scrapers.jobspy_scraper import JobspyPlan, JobspyScraper
from app.scrapers.platsbanken import PlatsbankenScraper
from app.scrapers.query_builder import build_search_queries
from app.scrapers.remotive import RemotiveScraper
from app.scrapers.tecnoempleo import TecnoempleoScraper
from app.scrapers.weworkremotely import WeWorkRemotelyScraper

logger = logging.getLogger(__name__)

# Scrapers propios ya implementados, indexados por el `scraper_class` del catalogo.
SCRAPER_BY_ID: dict[str, type[BaseScraper]] = {
    "RemotiveScraper": RemotiveScraper,
    "TecnoempleoScraper": TecnoempleoScraper,
    "PlatsbankenScraper": PlatsbankenScraper,
    "WeWorkRemotelyScraper": WeWorkRemotelyScraper,
    "HackerNewsWhoIsHiringScraper": HackerNewsWhoIsHiringScraper,
    "ArbeitnowScraper": ArbeitnowScraper,
    "AdzunaScraper": AdzunaScraper,
}

_DYNAMIC_KEYS = ("regions", "region_preset", "platforms", "queries")


@lru_cache(maxsize=1)
def load_catalog() -> list[dict]:
    """Carga platforms.json (cacheado). Devuelve la lista de plataformas."""
    path = settings.platforms_catalog_file
    if not path.exists():
        logger.warning("platforms.json no encontrado en %s", path)
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    return data.get("platforms", [])


def _has_dynamic_config(prefs: dict) -> bool:
    for k in _DYNAMIC_KEYS:
        v = prefs.get(k)
        if v:  # lista/dict no vacios o string no vacio
            return True
    return False


def _covers(platform_countries: list[str], regions: list[str]) -> bool:
    pc = set(platform_countries)
    rg = set(regions)
    if "REMOTE" in pc and "REMOTE" in rg:
        return True
    if "EU" in pc and any(r in EU_COUNTRIES for r in rg):
        return True
    return bool(pc & rg)


def _enabled(platform: dict, prefs: dict) -> bool:
    pid = platform["id"]
    plat_prefs = prefs.get("platforms") or {}
    if pid in plat_prefs:
        if not bool(plat_prefs[pid]):
            return False
    elif not platform.get("enabled_by_default"):
        return False
    # Autodesactivar si requiere una clave de entorno que no esta configurada.
    req = platform.get("requires_env")
    if req and not getattr(settings, req, ""):
        return False
    return True


def suggest_platforms(regions: list[str]) -> list[dict]:
    """Plataformas del catalogo que cubren las regiones dadas (para la UI)."""
    return [p for p in load_catalog() if _covers(p.get("countries", []), regions)]


def active_platforms(prefs: dict, regions: list[str]) -> list[dict]:
    """Plataformas activas = cubren region AND habilitadas AND con env disponible."""
    return [
        p
        for p in load_catalog()
        if _covers(p.get("countries", []), regions) and _enabled(p, prefs)
    ]


def _home_country(cv: dict | None, regions: list[str]) -> str:
    """Pais base para las busquedas remotas de Indeed (jobspy siempre exige uno).

    Devuelve SIEMPRE un nombre que jobspy entienda (via `country_map`), nunca
    texto libre del CV: `personal.location` suele venir como "Ciudad, Provincia
    (Pais)" y pasarle eso a jobspy no resuelve a ningun pais.

    Prioridad: region-pais elegida > preferred_countries > pais del CV > España.
    """
    candidates: list[str] = [r for r in regions if r != "REMOTE"]

    prefs = ((cv or {}).get("search_preferences") or {})
    candidates += [c for c in (prefs.get("preferred_countries") or []) if isinstance(c, str)]

    # Ultimo recurso: buscar un codigo/nombre de pais dentro de `personal.location`.
    loc = (((cv or {}).get("personal") or {}).get("location") or "").lower()
    if "españa" in loc or "spain" in loc:
        candidates.append("ES")

    for c in candidates:
        params = jobspy_params_for(c.strip().upper())
        if params and params.get("country_indeed"):
            return params["country_indeed"]

    return "Spain"


def build_jobspy_plans(
    regions: list[str],
    queries: list[str],
    sites: list[str],
    prefs: dict,
    home_country: str = "Spain",
) -> list[JobspyPlan]:
    results = int(prefs.get("results_per_query", 20) or 20)
    hours = int(prefs.get("hours_old", 72) or 72)
    plans: list[JobspyPlan] = []
    seen: set[tuple] = set()
    remote = False

    for r in regions:
        if r == "REMOTE":
            remote = True
            continue
        params = jobspy_params_for(r)
        if not params:
            continue
        key = (params["location"], params["country_indeed"])
        if key in seen:
            continue
        seen.add(key)
        plans.append(
            JobspyPlan(
                sites=sites,
                queries=queries,
                location=params["location"],
                country_indeed=params["country_indeed"],
                results_wanted=results,
                hours_old=hours,
            )
        )

    # Busqueda remota. Glassdoor exige pais y ciudad, asi que lo excluimos aqui.
    # Indeed SI se queda: le pasamos el pais base del usuario + is_remote=True.
    # (Antes se mandaba country_indeed=None y jobspy caia a "usa" por defecto:
    # una busqueda "remoto worldwide" acababa trayendo ofertas de EE.UU.)
    if remote:
        rsites = [s for s in sites if s != "glassdoor"]
        if rsites:
            plans.append(
                JobspyPlan(
                    sites=rsites,
                    queries=queries,
                    location="",
                    country_indeed=home_country,
                    results_wanted=results,
                    hours_old=hours,
                    is_remote=True,
                )
            )
    return plans


def build_active_scrapers(cv: dict | None, prefs: dict | None) -> list[BaseScraper]:
    """Construye las instancias de scraper a ejecutar segun las preferencias.

    Devuelve el conjunto legacy si no hay configuracion dinamica (retrocompat).
    """
    prefs = prefs or {}

    if not _has_dynamic_config(prefs):
        from app.scrapers import ALL_SCRAPERS

        return [cls() for cls in ALL_SCRAPERS]

    regions = resolve_regions(prefs)
    if not regions:
        from app.scrapers import ALL_SCRAPERS

        return [cls() for cls in ALL_SCRAPERS]

    queries = build_search_queries(cv or {}, prefs)
    active = active_platforms(prefs, regions)
    instances: list[BaseScraper] = []

    jobspy_sites = sorted(
        {
            p["jobspy_site"]
            for p in active
            if p.get("method") == "jobspy" and p.get("jobspy_site")
        }
    )
    if jobspy_sites and queries:
        plans = build_jobspy_plans(
            regions, queries, jobspy_sites, prefs, home_country=_home_country(cv, regions)
        )
        if plans:
            instances.append(JobspyScraper(plans))

    skipped: list[str] = []
    for p in active:
        if p.get("method") == "jobspy":
            continue  # ya cubierto arriba
        if p.get("method") == "apply_only":
            continue  # por diseño no aporta ofertas
        # Cualquier plataforma con un scraper propio implementado (method
        # "scraper" o "api").
        cls_name = p.get("scraper_class")
        cls = SCRAPER_BY_ID.get(cls_name) if cls_name else None
        if cls is None:
            # Declarada en el catalogo pero SIN implementacion. Antes se ignoraba
            # en silencio y el usuario creia que estaba buscando ahi.
            skipped.append(p["id"])
            continue
        inst = cls()
        inst.configure(regions=regions, queries=queries, prefs=prefs)
        instances.append(inst)

    if skipped:
        logger.warning(
            "registry: plataformas SIN scraper implementado, no se buscara en ellas: %s. "
            "Estan marcadas como 'planned' en platforms.json.",
            skipped,
        )

    if not instances:
        # NO caemos a ALL_SCRAPERS: eso scrapeaba portales de OTROS paises
        # (p.ej. pedir solo Holanda y acabar recibiendo ofertas de Tecnoempleo).
        # Preferimos devolver 0 ofertas y que se vea, a devolver ofertas erroneas.
        logger.error(
            "registry: NINGUNA plataforma activa con scraper para regiones=%s "
            "(seleccionadas=%s, sin implementar=%s). 0 ofertas: revisa tu seleccion.",
            regions,
            [p["id"] for p in active],
            skipped,
        )
        return []

    logger.info(
        "registry: %d scrapers activos (regiones=%s, plataformas=%s)",
        len(instances),
        regions,
        [p["id"] for p in active if p.get("scraper_class") or p.get("jobspy_site")],
    )
    return instances

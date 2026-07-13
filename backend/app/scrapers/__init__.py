"""Modulo de scrapers."""

from app.scrapers.arbeitnow import ArbeitnowScraper
from app.scrapers.base import BaseScraper, compute_job_hash
from app.scrapers.hackernews_jobs import HackerNewsWhoIsHiringScraper
from app.scrapers.jobspy_scraper import JobspyScraper
from app.scrapers.remotive import RemotiveScraper
from app.scrapers.sysadmin_scraper import SysAdminScraper
from app.scrapers.tecnoempleo import TecnoempleoScraper

# Conjunto usado SOLO en modo legacy (instalacion sin onboarding completado).
# Una vez hay `search_preferences` dinamicas, manda `registry.build_active_scrapers`
# y el conjunto sale del catalogo `platforms.json`. Ojo: SysAdminScraper solo vive
# aqui — en modo dinamico sus queries las cubre `query_builder` a partir de los
# roles del CV.
ALL_SCRAPERS: list[type[BaseScraper]] = [
    RemotiveScraper,
    TecnoempleoScraper,
    JobspyScraper,
    SysAdminScraper,
    HackerNewsWhoIsHiringScraper,
    ArbeitnowScraper,
]

__all__ = [
    "ALL_SCRAPERS",
    "ArbeitnowScraper",
    "BaseScraper",
    "HackerNewsWhoIsHiringScraper",
    "JobspyScraper",
    "RemotiveScraper",
    "SysAdminScraper",
    "TecnoempleoScraper",
    "compute_job_hash",
]

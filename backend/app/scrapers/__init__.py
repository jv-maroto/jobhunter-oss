"""Modulo de scrapers."""

from app.scrapers.base import BaseScraper, compute_job_hash
from app.scrapers.jobspy_scraper import JobspyScraper
from app.scrapers.remotive import RemotiveScraper
from app.scrapers.sysadmin_scraper import SysAdminScraper
from app.scrapers.tecnoempleo import TecnoempleoScraper

# RemoteOK eliminado del pipeline: requiere cuenta + paywall en ofertas premium.

ALL_SCRAPERS: list[type[BaseScraper]] = [
    RemotiveScraper,
    TecnoempleoScraper,
    JobspyScraper,
    SysAdminScraper,
]

__all__ = [
    "ALL_SCRAPERS",
    "BaseScraper",
    "JobspyScraper",
    "RemotiveScraper",
    "SysAdminScraper",
    "TecnoempleoScraper",
    "compute_job_hash",
]

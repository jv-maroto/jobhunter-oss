"""Bounded manual searches with isolated preferences and persistent outcomes."""
import asyncio
from copy import deepcopy
from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import select

from app.db import SessionLocal
from app.models.job import Job
from app.models.search_campaign import SearchCampaign
from app.profile_store import read_profile
from app.scrapers.country_map import COUNTRY_MAP
from app.scrapers.jobspy_scraper import JobspyScraper
from app.scrapers.registry import build_jobspy_plans


def stamp():
    return datetime.now(timezone.utc).isoformat()


def campaign_profile(campaign, profile):
    cv = deepcopy(profile)
    prefs = dict(cv.get("search_preferences") or {})
    prefs.update(regions=list(campaign.countries), roles=list(campaign.roles),
                 remote_only=campaign.modality == "remote", residence_country=campaign.residence_country or "",
                 queries_auto=False, queries=list(campaign.roles), max_queries=campaign.max_queries,
                 results_per_query=campaign.results_per_query)
    cv["search_preferences"] = prefs
    return cv


def validate_run(campaign):
    if campaign.status == "archived":
        raise ValueError("Archived campaigns cannot run")
    unsupported = sorted(set(campaign.countries) - set(COUNTRY_MAP))
    if unsupported:
        raise ValueError("Countries without configured connectors: " + ", ".join(unsupported))
    if not campaign.roles or not campaign.countries:
        raise ValueError("Select at least one role and country")
    if campaign.modality in {"hybrid", "onsite"}:
        raise ValueError("Hybrid-only and onsite-only filtering require explicit connector metadata and are not supported yet")
    if len(campaign.roles) * len(campaign.countries) > campaign.max_queries:
        raise ValueError("Role × country queries exceed max_queries; narrow the campaign or raise its budget")


def reserve_run(campaign):
    validate_run(campaign)
    if campaign.last_run and campaign.last_run.get("status") == "running":
        raise RuntimeError("Campaign is already running")
    campaign.last_run = {"id": uuid4().hex, "status": "running", "started_at": stamp()}
    return campaign.last_run


def recover_interrupted_runs():
    with SessionLocal() as db:
        for row in db.scalars(select(SearchCampaign)):
            if row.last_run and row.last_run.get("status") == "running":
                row.last_run = {**row.last_run, "status": "interrupted", "finished_at": stamp(),
                                "error": "Backend restarted before this run completed"}
        db.commit()


async def run_campaign(campaign_id: int):
    from app.services import filter_scraped_jobs, ingest_scraped_jobs

    with SessionLocal() as db:
        row = db.get(SearchCampaign, campaign_id)
        if row is None:
            return
        started = dict(row.last_run or {})
        try:
            cv = campaign_profile(row, read_profile())
            prefs = cv["search_preferences"]
            # One site so max_queries bounds actual role-country requests.
            plans = build_jobspy_plans(row.countries, row.roles, ["indeed"], prefs)
            scraped = await JobspyScraper(plans).fetch()
            scraped_count = len(scraped)
            scraped, filtered = filter_scraped_jobs(scraped, prefs)
            inserted, duplicates = await asyncio.to_thread(ingest_scraped_jobs, db, scraped, cv_override=cv)
            hashes = {job.hash for job in scraped}
            ids = list(db.scalars(select(Job.id).where(Job.hash.in_(hashes)))) if hashes else []
            row.last_run = {**started, "status": "finished", "finished_at": stamp(),
                            "scraped": scraped_count, "eligible": len(scraped), "filtered": filtered, "inserted": inserted, "duplicates": duplicates,
                            "job_ids": ids, "connector_health": "unverified", "note": "Shared job inventory: new jobs evaluated with campaign preferences; existing scores may come from other searches. Connector health is unverified (zero results can include source errors). Languages and residence restrictions need individual review."}
        except Exception:
            db.rollback()
            row = db.get(SearchCampaign, campaign_id)
            row.last_run = {**started, "status": "failed", "finished_at": stamp(),
                            "error": "Campaign search failed; review backend logs and connector configuration"}
            import logging
            logging.getLogger(__name__).exception("Campaign %s failed", campaign_id)
        db.commit()

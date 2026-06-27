"""Scheduler APScheduler: scraping cada 6h, posts semanales, personas Monday."""

from __future__ import annotations

import asyncio
import logging
from datetime import date as date_t
from datetime import datetime, timedelta

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from app.ai.connection_message import generate_connection_message
from app.ai.post_generator import generate_weekly_posts
from app.config import settings
from app.db import SessionLocal
from app.models.person import Person
from app.models.post import Post
from app.services import load_cv_master, scrape_and_ingest

logger = logging.getLogger(__name__)

_scheduler: AsyncIOScheduler | None = None


async def _job_scrape() -> None:
    logger.info("scheduler: running scrape+ingest")
    db = SessionLocal()
    try:
        result = await scrape_and_ingest(db)
        logger.info("scheduler: scrape result %s", result)
    except Exception as exc:  # noqa: BLE001
        logger.exception("scheduler scrape failed: %s", exc)
    finally:
        db.close()


async def _job_gmail_sync() -> None:
    """Sincroniza Gmail si esta habilitado y conectado (Pilar 4)."""
    from app.integrations.gmail.clients import get_client
    from app.integrations.gmail.sync import run_sync

    if get_client() is None:
        return
    logger.info("scheduler: running gmail sync")
    db = SessionLocal()
    try:
        result = await asyncio.to_thread(run_sync, db)
        logger.info("scheduler: gmail sync %s", result)
    except Exception as exc:  # noqa: BLE001
        logger.exception("gmail sync failed: %s", exc)
    finally:
        db.close()


def _dummy_persons() -> list[dict[str, str]]:
    """Datos placeholder hasta tener scraping LinkedIn real."""
    return [
        {
            "full_name": "Recruiter Tech Madrid",
            "headline": "Senior Tech Recruiter",
            "company": "TechCo Madrid",
            "profile_url": "https://linkedin.com/in/placeholder-tech-madrid",
            "reason": "Placeholder: recruiter Python Madrid",
            "priority": "85",
        },
        {
            "full_name": "Backend Lead Barcelona",
            "headline": "Backend Engineering Lead",
            "company": "Saas Barcelona",
            "profile_url": "https://linkedin.com/in/placeholder-backend-bcn",
            "reason": "Placeholder: lead backend Python remoto",
            "priority": "70",
        },
    ]


def _job_persons_weekly() -> None:
    """Cada lunes 06:00: genera lista de 20 personas para contactar."""
    logger.info("scheduler: generating weekly persons list")
    db = SessionLocal()
    try:
        cv = load_cv_master()
        for raw in _dummy_persons():
            existing = (
                db.query(Person).filter(Person.profile_url == raw["profile_url"]).one_or_none()
            )
            if existing is not None:
                continue
            msg = generate_connection_message(
                target_person={
                    "full_name": raw["full_name"],
                    "headline": raw["headline"],
                    "company": raw["company"],
                },
                profile_owner=cv,
                language="es",
            )
            p = Person(
                full_name=raw["full_name"],
                headline=raw["headline"],
                company=raw["company"],
                profile_url=raw["profile_url"],
                reason=raw["reason"],
                message=msg,
                priority=int(raw["priority"]),
                status="pending",
            )
            db.add(p)
        db.commit()
    except Exception as exc:  # noqa: BLE001
        logger.exception("persons weekly job failed: %s", exc)
        db.rollback()
    finally:
        db.close()


def _job_posts_weekly() -> None:
    """Cada domingo 18:00: genera 7 posts para la semana siguiente."""
    logger.info("scheduler: generating weekly posts")
    db = SessionLocal()
    try:
        cv = load_cv_master()
        posts = generate_weekly_posts(cv, theme="weekly mix", count=7, language="es")
        start = date_t.today() + timedelta(days=1)
        for i, p in enumerate(posts):
            row = Post(
                date=start + timedelta(days=i),
                topic=str(p.get("topic", "Untitled")),
                content=str(p.get("content", "")),
                hashtags=list(p.get("hashtags", []) or []),
                image_prompt=p.get("image_prompt"),
                status="draft",
            )
            db.add(row)
        db.commit()
    except Exception as exc:  # noqa: BLE001
        logger.exception("posts weekly job failed: %s", exc)
        db.rollback()
    finally:
        db.close()


def start_scheduler() -> AsyncIOScheduler | None:
    """Arranca scheduler. Idempotente."""
    global _scheduler
    if not settings.enable_scheduler:
        logger.info("scheduler disabled by config")
        return None
    if _scheduler is not None:
        return _scheduler

    sched = AsyncIOScheduler(timezone="Europe/Madrid")

    sched.add_job(
        _job_scrape,
        IntervalTrigger(hours=settings.scrape_interval_hours),
        id="scrape_all",
        replace_existing=True,
        next_run_time=datetime.now() + timedelta(seconds=30),
    )
    sched.add_job(
        _job_persons_weekly,
        CronTrigger(day_of_week="mon", hour=6, minute=0),
        id="persons_weekly",
        replace_existing=True,
    )
    sched.add_job(
        _job_posts_weekly,
        CronTrigger(day_of_week="sun", hour=18, minute=0),
        id="posts_weekly",
        replace_existing=True,
    )

    if settings.enable_gmail_tracking:
        sched.add_job(
            _job_gmail_sync,
            IntervalTrigger(minutes=settings.gmail_sync_interval_minutes),
            id="gmail_sync",
            replace_existing=True,
            next_run_time=datetime.now() + timedelta(seconds=60),
        )

    sched.start()
    _scheduler = sched
    logger.info("scheduler started (scrape every %dh)", settings.scrape_interval_hours)
    return sched


def stop_scheduler() -> None:
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None


# Util para uso manual desde scripts
def trigger_scrape_sync() -> dict:
    return asyncio.run(_trigger_scrape_async())


async def _trigger_scrape_async() -> dict:
    db = SessionLocal()
    try:
        return await scrape_and_ingest(db)
    finally:
        db.close()

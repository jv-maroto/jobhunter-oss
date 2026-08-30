"""Scheduler APScheduler: scraping periodico, posts semanales, sync Gmail."""

from __future__ import annotations

import asyncio
import logging
from datetime import date as date_t
from datetime import datetime, timedelta, timezone

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from app.ai.post_generator import generate_weekly_posts
from app.config import settings
from app.db import SessionLocal
from app.models.post import Post
from app.onboarding.detect import is_onboarded
from app.services import load_cv_master, scrape_and_ingest

logger = logging.getLogger(__name__)

_scheduler: AsyncIOScheduler | None = None


async def _job_scrape() -> None:
    if not is_onboarded():
        # Sin perfil no hay regiones ni queries reales: scrapear con la plantilla
        # llenaba la DB de ofertas de cualquier pais antes de que el usuario
        # dijera quien es.
        logger.info("scheduler: onboarding pendiente, scrape omitido")
        return
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


def _job_posts_weekly() -> None:
    """Cada domingo 18:00: genera 7 posts para la semana siguiente."""
    if not settings.enable_post_generation:
        return
    if not is_onboarded():
        logger.info("scheduler: onboarding pendiente, posts semanales omitidos")
        return
    logger.info("scheduler: generating weekly posts")
    db = SessionLocal()
    try:
        cv = load_cv_master()
        posts = generate_weekly_posts(
            cv, theme="weekly mix", count=7, language=settings.content_language
        )
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

    sched = AsyncIOScheduler(timezone=settings.scheduler_timezone)

    sched.add_job(
        _job_scrape,
        IntervalTrigger(hours=settings.scrape_interval_hours),
        id="scrape_all",
        replace_existing=True,
        next_run_time=datetime.now(timezone.utc) + timedelta(seconds=30),
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
            next_run_time=datetime.now(timezone.utc) + timedelta(seconds=60),
        )

    sched.start()
    _scheduler = sched
    logger.info(
        "scheduler started (scrape every %dh, tz=%s)",
        settings.scrape_interval_hours,
        settings.scheduler_timezone,
    )
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

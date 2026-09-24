import asyncio
from unittest.mock import AsyncMock

from app import scheduler


def test_scheduled_search_uses_discovery_without_paid_pipeline(monkeypatch):
    from app import discovery
    monkeypatch.setattr(scheduler, "is_onboarded", lambda: True)
    monkeypatch.setattr(discovery, "reserve_discovery", lambda: True)
    run = AsyncMock()
    monkeypatch.setattr(discovery, "run_discovery", run)
    asyncio.run(scheduler._job_scrape())
    run.assert_awaited_once()


def test_paid_weekly_generation_disabled_without_explicit_config(monkeypatch):
    monkeypatch.setattr(scheduler.settings, "automatic_ai_enabled", False)
    monkeypatch.setattr(scheduler.settings, "enable_post_generation", True)
    monkeypatch.setattr(scheduler, "generate_weekly_posts", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("No paid generation")))
    scheduler._job_posts_weekly()


def test_manual_search_uses_free_discovery(monkeypatch):
    from app import discovery
    monkeypatch.setattr(discovery, "reserve_discovery", lambda: True)
    run = AsyncMock()
    monkeypatch.setattr(discovery, "run_discovery", run)
    monkeypatch.setattr(discovery, "discovery_status", lambda: {"running": False})
    assert scheduler.trigger_scrape_sync() == {"running": False}
    run.assert_awaited_once()


def test_manual_search_reuses_running_discovery(monkeypatch):
    from app import discovery
    monkeypatch.setattr(discovery, "reserve_discovery", lambda: False)
    run = AsyncMock()
    monkeypatch.setattr(discovery, "run_discovery", run)
    monkeypatch.setattr(discovery, "discovery_status", lambda: {"running": True})
    assert scheduler.trigger_scrape_sync() == {"running": True}
    run.assert_not_awaited()

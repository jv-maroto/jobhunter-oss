from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from app.api.jobs import scrape_status
from app.scheduler import _job_scrape
from app.services import scrape_and_ingest, scrape_runtime_state


def test_scheduler_is_visible_and_blocks_overlapping_manual_scrape():
    async def scenario():
        started, release = asyncio.Event(), asyncio.Event()
        calls = []

        async def pipeline(db):
            calls.append(db)
            started.set()
            await release.wait()
            return {"scraped": 7, "inserted": 2, "duplicates": 5}

        scheduler_db = SimpleNamespace(close=lambda: None)
        with patch("app.services._scrape_and_ingest", side_effect=pipeline), patch("app.scheduler.is_onboarded", return_value=True), patch("app.scheduler.SessionLocal", return_value=scheduler_db):
            task = asyncio.create_task(_job_scrape())
            await started.wait()
            state = scrape_status()
            assert state["running"] is True and state["trigger"] == "scheduler"
            assert state["finished_at"] is None
            duplicate = await scrape_and_ingest(SimpleNamespace())
            assert duplicate["status"] == "already_running"
            assert calls == [scheduler_db]
            release.set()
            await task
        state = scrape_status()
        assert state["running"] is False and state["phase"] == "finished"
        assert state["scraped"] == 7 and state["inserted"] == 2
        assert state["finished_at"] is not None

    asyncio.run(scenario())


def test_cancelled_caller_keeps_guard_until_pipeline_finishes():
    async def scenario():
        started, release = asyncio.Event(), asyncio.Event()

        async def pipeline(db):
            started.set()
            await release.wait()
            return {"scraped": 1, "inserted": 1, "duplicates": 0}

        with patch("app.services._scrape_and_ingest", side_effect=pipeline):
            caller = asyncio.create_task(scrape_and_ingest(SimpleNamespace()))
            await started.wait()
            caller.cancel()
            await asyncio.sleep(0)
            assert not caller.done() and scrape_runtime_state()["running"] is True
            assert (await scrape_and_ingest(SimpleNamespace()))["status"] == "already_running"
            release.set()
            with pytest.raises(asyncio.CancelledError):
                await caller
        assert scrape_runtime_state()["running"] is False
        assert scrape_runtime_state()["phase"] == "finished"
        assert scrape_runtime_state()["inserted"] == 1

    asyncio.run(scenario())


def test_failure_clears_guard_and_next_run_clears_stale_error():
    async def scenario():
        with patch("app.services._scrape_and_ingest", side_effect=RuntimeError("source failure")):
            with pytest.raises(RuntimeError):
                await scrape_and_ingest(SimpleNamespace())
        assert scrape_runtime_state()["running"] is False
        assert scrape_runtime_state()["phase"] == "failed"
        with patch("app.services._scrape_and_ingest", return_value={"scraped": 0, "inserted": 0, "duplicates": 0}):
            await scrape_and_ingest(SimpleNamespace())
        assert scrape_runtime_state()["error"] is None
        assert scrape_runtime_state()["phase"] == "finished"

    asyncio.run(scenario())

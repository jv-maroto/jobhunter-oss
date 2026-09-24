import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException

from app.api import jobs


def test_unverified_indeed_does_not_spend_on_documents(monkeypatch):
    job = SimpleNamespace(source="indeed", source_url="https://es.indeed.com/viewjob?jk=test", availability=None, title="Engineer", company="Demo", description="Description")
    db = SimpleNamespace(get=lambda *args: job, commit=lambda: None)
    prepare = AsyncMock()
    monkeypatch.setattr(jobs, "_prepare_application", prepare)
    monkeypatch.setattr("app.job_availability.check_listing", AsyncMock(return_value={"status":"unverified"}))
    with pytest.raises(HTTPException) as error:
        asyncio.run(jobs.prepare_application.__wrapped__(None, 100, db))
    assert error.value.status_code == 422
    prepare.assert_not_awaited()
    assert 100 not in jobs._PREPARING_JOBS


def test_overlapping_preparation_rejected_and_failure_releases_guard(monkeypatch):
    async def scenario():
        entered, release = asyncio.Event(), asyncio.Event()
        job = SimpleNamespace(source="manual", source_url="https://example.com", availability=None)
        db = SimpleNamespace(get=lambda *args: job)
        async def prepare(*args):
            entered.set()
            await release.wait()
            raise RuntimeError("Generation failed")
        monkeypatch.setattr(jobs, "_prepare_application", prepare)
        first = asyncio.create_task(jobs.prepare_application.__wrapped__(None, 101, db))
        await asyncio.wait_for(entered.wait(), 1)
        try:
            with pytest.raises(HTTPException) as error:
                await jobs.prepare_application.__wrapped__(None, 101, db)
            assert error.value.status_code == 409
        finally:
            release.set()
            with pytest.raises(RuntimeError):
                await first
        assert 101 not in jobs._PREPARING_JOBS
    asyncio.run(scenario())

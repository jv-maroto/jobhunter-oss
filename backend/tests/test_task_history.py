import asyncio
from types import SimpleNamespace
from unittest.mock import patch

from app import services
from app.db import SessionLocal, init_db
from app.models.task_run import TaskRun
from app.task_history import begin_task, recover_latest


def test_startup_marks_unfinished_search_interrupted():
    init_db()
    task_id = begin_task("recovery-test", {"running": True, "scraped": 12})
    state = recover_latest("recovery-test")
    assert state["task_id"] == task_id
    assert state["running"] is False
    assert state["phase"] == "interrupted"
    assert state["scraped"] == 12
    assert recover_latest("recovery-test") == state


def test_reservation_prevents_double_click_and_completed_state_survives_memory_loss():
    init_db()
    assert services.reserve_scrape()
    first_id = services.scrape_runtime_state()["task_id"]
    assert not services.reserve_scrape()
    try:
        with patch("app.services._scrape_and_ingest", return_value={
            "scraped": 7, "inserted": 2, "duplicates": 5,
        }):
            asyncio.run(services.scrape_and_ingest(SimpleNamespace(), reserved=True))
    finally:
        if services._SCRAPE_LOCK.locked():
            services._SCRAPE_LOCK.release()
    services._SCRAPE_STATE.update({"scraped": 0, "phase": "idle"})
    services.restore_scrape_runtime()
    state = services.scrape_runtime_state()
    assert state["task_id"] == first_id
    assert state["phase"] == "finished"
    assert state["scraped"] == 7
    with SessionLocal() as db:
        assert db.get(TaskRun, first_id).status == "finished"

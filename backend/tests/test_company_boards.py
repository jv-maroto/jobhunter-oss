import asyncio

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.boards import router
from app.company_boards.readers import endpoint, fetch_board, parse_jobs
from app.db import get_db
from app.models.company_board import CompanyBoard


def test_three_contracts_keep_full_text_unknown_residence_and_pay():
    greenhouse = parse_jobs("greenhouse", {"jobs": [{"id": 1, "title": "Engineer", "absolute_url": "https://boards.greenhouse.io/demo/jobs/1", "content": "&lt;p&gt;Full requirements&lt;/p&gt;&lt;script&gt;bad()&lt;/script&gt;"}]}, "Demo")["jobs"][0]
    assert greenhouse["location"] == "" and greenhouse["remote"] is None
    assert greenhouse["description"] == "Full requirements"
    assert greenhouse["salary_min"] is None
    lever = parse_jobs("lever", [{"id": "a", "text": "Engineer", "hostedUrl": "https://jobs.lever.co/demo/a", "descriptionPlain": "Opening", "lists": [{"text": "Requirements", "content": "<li>Python</li>"}], "additionalPlain": "Closing", "salaryRange": {"min": 50000, "max": 70000, "interval": "year", "currency": "EUR"}}], "Demo")["jobs"][0]
    assert "Python" in lever["description"] and "Closing" in lever["description"]
    assert lever["salary_min"] == 50000 and lever["salary_period"] == "year"
    ashby = parse_jobs("ashby", {"jobs": [{"title": "Engineer", "jobUrl": "https://jobs.ashbyhq.com/demo/a", "location": "Tokyo", "descriptionPlain": "Full description", "isRemote": True, "compensation": {"summaryComponents": [{"compensationType": "EquityPercentage", "minValue": 1}, {"compensationType": "Salary", "minValue": 80000, "maxValue": 90000, "currencyCode": "USD", "interval": "1 YEAR"}]}}]}, "Demo")["jobs"][0]
    assert ashby["location"] == "Tokyo" and ashby["remote"] is True
    assert ashby["salary_min"] == 80000 and ashby["currency"] == "USD"


def test_fixed_hosts_invalid_slugs_and_redirects_are_rejected():
    for slug in ("../local", "https://localhost", "demo?x=1", "demo#x", "a/b"):
        with pytest.raises(ValueError):
            endpoint("lever", slug)
    seen = []
    def handler(request):
        seen.append(str(request.url))
        return httpx.Response(302, headers={"location": "http://127.0.0.1/private"})
    with pytest.raises(httpx.HTTPStatusError):
        asyncio.run(fetch_board("lever", "demo", "Demo", transport=httpx.MockTransport(handler)))
    assert len(seen) == 1 and seen[0].startswith("https://api.lever.co/")


def test_bounded_results_skip_unsafe_links_and_unlisted_jobs(monkeypatch):
    from app.company_boards import readers
    monkeypatch.setattr(readers, "MAX_JOBS", 2)
    row = {"title": "Engineer", "jobUrl": "https://jobs.ashbyhq.com/demo/a", "descriptionPlain": "A" * 100001}
    parsed = parse_jobs("ashby", {"jobs": [row, {**row, "jobUrl": "javascript:alert(1)"}, row]}, "Demo")
    assert parsed["truncated"] and parsed["skipped"] == 1
    assert parsed["jobs"][0]["description_truncated"]
    assert len(parsed["jobs"][0]["description"]) == 100000
    assert parse_jobs("ashby", {"jobs": [{**row, "isListed": False}]}, "Demo")["jobs"] == []
    with pytest.raises(ValueError):
        parse_jobs("greenhouse", {"error": "No board"}, "Demo")


def test_crud_refresh_preserves_snapshot_on_failure_and_restart(monkeypatch):
    from app.api import boards
    from app.company_boards import service
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    CompanyBoard.__table__.create(engine)
    sessions = sessionmaker(bind=engine, expire_on_commit=False)
    monkeypatch.setattr(service, "SessionLocal", sessions)
    app = FastAPI()
    app.include_router(router)
    def db():
        with sessions() as session:
            yield session
    app.dependency_overrides[get_db] = db
    async def fetch(*args):
        return {"jobs": [{"title": "Tokyo", "location": "", "remote": None}], "received": 1, "truncated": False}
    monkeypatch.setattr(service, "fetch_board", fetch)
    with TestClient(app) as client:
        row = client.post("/search/boards", json={"name": "Demo", "provider": "ashby", "slug": "demo"}).json()
        assert client.post("/search/boards", json={"name": "Demo", "provider": "ashby", "slug": "demo"}).status_code == 409
        url = f'/search/boards/{row["id"]}'
        assert client.post(url + "/refresh").status_code == 202
        result = client.get(url + "/jobs").json()
        assert result["last_refresh"]["status"] == "finished"
        assert result["jobs"][0]["location"] == ""
        async def failed(*args):
            raise ValueError("Invalid response")
        monkeypatch.setattr(service, "fetch_board", failed)
        assert client.post(url + "/refresh").status_code == 202
        result = client.get(url + "/jobs").json()
        assert result["last_refresh"]["status"] == "failed" and len(result["jobs"]) == 1
        async def pending(*args):
            pass
        monkeypatch.setattr(boards, "refresh_board", pending)
        assert client.post(url + "/refresh").status_code == 202
        assert client.post(url + "/refresh").status_code == 409
        assert client.delete(url).status_code == 409
        service.recover_interrupted_refreshes()
        assert client.get(url + "/jobs").json()["last_refresh"]["status"] == "interrupted"
        assert client.delete(url).json()["status"] == "archived"
        assert client.get("/search/boards").json() == []
    engine.dispose()

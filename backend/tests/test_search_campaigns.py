import asyncio
from copy import deepcopy

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.campaigns import router
from app.db import get_db
from app.models.search_campaign import SearchCampaign
from app.search_campaigns.catalog import COUNTRY_CODES
from app.search_campaigns.eligibility import evaluate_eligibility
from app.search_campaigns.runner import campaign_profile, validate_run


@pytest.fixture
def client():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    SearchCampaign.__table__.create(engine)
    sessions = sessionmaker(bind=engine, expire_on_commit=False)
    app = FastAPI()
    app.include_router(router)
    def db():
        with sessions() as session:
            yield session
    app.dependency_overrides[get_db] = db
    with TestClient(app) as client:
        yield client
    engine.dispose()


def test_global_crud_validates_without_assuming_coverage(client):
    assert len(COUNTRY_CODES) == 249
    response = client.post("/search/campaigns", json={"name": "World", "countries": ["jp", "US", "jp"], "roles": ["Developer"]})
    assert response.status_code == 201
    row = response.json()
    assert row["countries"] == ["JP", "US"]
    assert row["residence_country"] is None
    assert client.patch(f'/search/campaigns/{row["id"]}', json={"countries": ["ES"], "max_queries": 2}).status_code == 200
    assert client.patch(f'/search/campaigns/{row["id"]}', json={"max_queries": 0}).status_code == 422
    assert client.post("/search/campaigns", json={"name": "Bad", "countries": ["ZZ"]}).status_code == 422
    assert client.delete(f'/search/campaigns/{row["id"]}').json()["status"] == "archived"
    assert client.get("/search/campaigns").json() == []
    assert len(client.get("/search/campaigns?include_archived=true").json()) == 1
    countries = {r["code"]: r for r in client.get("/search/coverage").json()["countries"]}
    assert countries["JP"]["configured_connectors"] == ["jobspy"]
    assert countries["IS"]["configured_connectors"] == []
    assert countries["ES"]["status"] == "configured_not_verified"


def test_remote_us_is_not_remote_from_spain_and_unknown_stays_unknown():
    assert evaluate_eligibility("ES", ["US"])["status"] == "no"
    assert evaluate_eligibility("ES", ["ES"])["status"] == "yes"
    assert evaluate_eligibility(None, ["US"])["status"] == "unknown"
    assert evaluate_eligibility("ES")["status"] == "unknown"
    assert evaluate_eligibility("ES", worldwide_explicit=True)["status"] == "yes"
    assert evaluate_eligibility("ES", ["US"], worldwide_explicit=True)["status"] == "unknown"


def test_campaign_overrides_are_isolated_and_queries_budgeted():
    row = SearchCampaign(name="Test", countries=["DE"], roles=["Python"], modality="remote", residence_country=None, max_queries=1, results_per_query=10, status="draft")
    profile = {"search_preferences": {"regions": ["ES"], "roles": ["PHP"], "salary_min_eur": 30000}}
    before = deepcopy(profile)
    cv = campaign_profile(row, profile)
    assert profile == before
    assert cv["search_preferences"]["regions"] == ["DE"]
    assert cv["search_preferences"]["residence_country"] == ""
    validate_run(row)
    row.countries = ["ES", "DE"]
    with pytest.raises(ValueError, match="budget"):
        validate_run(row)
    row.countries = ["IS"]
    with pytest.raises(ValueError, match="IS"):
        validate_run(row)


def test_unsupported_run_is_explicit_and_does_not_start(client):
    row = client.post("/search/campaigns", json={"name": "Iceland", "countries": ["IS"], "roles": ["Python"]}).json()
    response = client.post(f'/search/campaigns/{row["id"]}/run')
    assert response.status_code == 422
    assert "IS" in response.json()["detail"]
    assert client.get("/search/campaigns").json()[0]["last_run"] is None


def test_supported_run_claims_persistently_and_rejects_duplicate(client, monkeypatch):
    calls = []
    async def fake_run(campaign_id):
        calls.append(campaign_id)
    monkeypatch.setattr("app.search_campaigns.runner.run_campaign", fake_run)
    row = client.post("/search/campaigns", json={"name": "Spain", "countries": ["ES"], "roles": ["Python"]}).json()
    response = client.post(f'/search/campaigns/{row["id"]}/run')
    assert response.status_code == 202, response.text
    assert calls == [row["id"]]
    assert client.get("/search/campaigns").json()[0]["last_run"]["status"] == "running"
    assert client.post(f'/search/campaigns/{row["id"]}/run').status_code == 409
    assert client.delete(f'/search/campaigns/{row["id"]}').status_code == 409


def test_runner_uses_isolated_profile_and_recovers_restart(tmp_path, monkeypatch):
    from app.search_campaigns import runner

    engine = create_engine(f"sqlite:///{tmp_path / 'campaign.db'}", connect_args={"check_same_thread": False})
    SearchCampaign.__table__.create(engine)
    sessions = sessionmaker(bind=engine, expire_on_commit=False)
    monkeypatch.setattr(runner, "SessionLocal", sessions)
    profile = {"search_preferences": {"regions": ["ES"]}}
    before = deepcopy(profile)
    monkeypatch.setattr(runner, "read_profile", lambda: profile)
    async def fetch(self):
        assert self._plans[0].country_indeed == "Germany"
        return []
    monkeypatch.setattr(runner.JobspyScraper, "fetch", fetch)
    captured = []
    def ingest(db, jobs, *, cv_override=None, **kwargs):
        captured.append(cv_override)
        return 0, 0
    monkeypatch.setattr("app.services.ingest_scraped_jobs", ingest)
    with sessions() as db:
        row = SearchCampaign(name="DE", roles=["Python"], countries=["DE"], modality="remote", max_queries=1, results_per_query=10, status="draft")
        runner.reserve_run(row)
        db.add(row)
        db.commit()
        campaign_id = row.id
    asyncio.run(runner.run_campaign(campaign_id))
    assert profile == before
    assert captured[0]["search_preferences"]["regions"] == ["DE"]
    with sessions() as db:
        row = db.get(SearchCampaign, campaign_id)
        assert row.last_run["status"] == "finished"
        assert row.last_run["job_ids"] == []
        row.last_run = {"id": "restart", "status": "running"}
        db.commit()
    runner.recover_interrupted_runs()
    with sessions() as db:
        assert db.get(SearchCampaign, campaign_id).last_run["status"] == "interrupted"
    engine.dispose()


@pytest.mark.parametrize("first_action", ["edit", "run"])
def test_stale_campaign_revision_cannot_edit_or_start(tmp_path, monkeypatch, first_action):
    from fastapi import BackgroundTasks, HTTPException

    from app.api import campaigns

    engine = create_engine(f"sqlite:///{tmp_path / 'revision.db'}")
    SearchCampaign.__table__.create(engine)
    sessions = sessionmaker(bind=engine, expire_on_commit=False)
    with sessions() as db:
        row = campaigns.create_campaign(campaigns.CampaignIn(name="Original", roles=["Python"], countries=["ES"]), db)
        campaign_id = row.id
    with sessions() as stale, sessions() as fresh:
        old_row = stale.get(SearchCampaign, campaign_id)
        if first_action == "edit":
            campaigns.update_campaign(campaign_id, {"roles": ["SQL"]}, fresh)
        else:
            campaigns.start_campaign(campaign_id, BackgroundTasks(), fresh)
        # Reproduce an endpoint that read the row just before the other commit.
        monkeypatch.setattr(campaigns, "get_campaign", lambda *_: old_row)
        with pytest.raises(HTTPException) as exc:
            if first_action == "edit":
                campaigns.start_campaign(campaign_id, BackgroundTasks(), stale)
            else:
                campaigns.update_campaign(campaign_id, {"roles": ["Java"]}, stale)
        assert exc.value.status_code == 409
    with sessions() as db:
        current = db.get(SearchCampaign, campaign_id)
        assert current.roles == (["SQL"] if first_action == "edit" else ["Python"])
        assert (current.last_run or {}).get("status") == (None if first_action == "edit" else "running")
    engine.dispose()


def test_shared_ingestion_serializes_campaign_and_global_writes(monkeypatch):
    import threading
    from concurrent.futures import ThreadPoolExecutor

    from app import services

    first_entered = threading.Event()
    release_first = threading.Event()
    second_attempted = threading.Event()
    second_entered = threading.Event()
    contexts = []
    def ingest(db, jobs, *, cv_override=None, **kwargs):
        contexts.append(cv_override)
        if cv_override is None:
            first_entered.set()
            assert release_first.wait(2)
        else:
            second_entered.set()
        return 1, 0
    monkeypatch.setattr(services, "_ingest_scraped_jobs", ingest)
    def campaign():
        second_attempted.set()
        return services.ingest_scraped_jobs(None, [], cv_override={"campaign": True})
    with ThreadPoolExecutor(max_workers=2) as pool:
        global_run = pool.submit(services.ingest_scraped_jobs, None, [])
        assert first_entered.wait(2)
        campaign_run = pool.submit(campaign)
        assert second_attempted.wait(2)
        assert not second_entered.wait(0.05)
        release_first.set()
        assert global_run.result() == campaign_run.result() == (1, 0)
    assert contexts == [None, {"campaign": True}]

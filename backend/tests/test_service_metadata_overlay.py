from __future__ import annotations

from datetime import datetime
from unittest.mock import Mock

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.api import jobs
from app.db import Base
from app.models.job import Job
from app.schemas.job import JobImport, JobOut
from app.services import current_job_metadata, refresh_job_metadata


def candidate(seniority="junior"):
    return {"skills": {"professional": ["SQL", "Python"]},
            "search_preferences": {"roles": ["Data Engineer"], "regions": ["DE"], "seniority": seniority}}


def saved_job():
    return Job(id=1, source="manual", source_url="https://example.org/jobs/1", hash="metadata-overlay",
               title="Data Engineer", company="Example", location="Berlin, Germany", remote=False,
               description="SQL and Python required.", track="dev", predicted_salary_band="unknown",
               match_score=90, seniority_compatible=False, saved_by_user=True, status="detected",
               key_matches=[], missing_skills=[], personalization_hooks=[], created_at=datetime(2025, 1, 1))


@pytest.mark.parametrize("rescore", [False, True])
@pytest.mark.parametrize("seniority,expected", [("junior", False), (None, None), ("any", None), ("senior", None)])
def test_overlay_retains_relevant_false_flags_but_drops_obsolete_preferences(rescore, seniority, expected):
    job = saved_job()
    before = dict(vars(job))
    metadata = current_job_metadata(job, candidate(seniority), rescore=rescore)
    assert metadata["seniority_compatible"] is expected
    if expected is False:
        assert metadata["match_score"] < 30
    assert vars(job) == before
    public = JobOut.model_validate(job).model_copy(update=metadata).model_dump()
    assert public["qualification_assessment"]["checks"]
    assert "qualification_assessment" not in Job.__table__.columns
    assert not hasattr(job, "qualification_assessment")


def test_refresh_writes_only_mapped_metadata_and_keeps_computed_assessment_in_overlay(monkeypatch):
    job = saved_job()
    db = Mock()
    db.scalars.return_value.all.return_value = [job]
    db.is_modified.return_value = True
    score_job = Mock(side_effect=AssertionError("Metadata refresh must not call AI"))
    monkeypatch.setattr("app.services.score_job", score_job)
    assert refresh_job_metadata(db, candidate()) == {"examined": 1, "updated": 1}
    assert job.seniority_compatible is False and job.match_score < 30
    assert not hasattr(job, "qualification_assessment")
    assert current_job_metadata(job, candidate())["qualification_assessment"]["checks"]
    assert job.saved_by_user is True and job.status == "detected"
    score_job.assert_not_called()
    db.commit.assert_called_once_with()


def test_manual_import_exposes_current_qualification_assessment_without_storing_it(monkeypatch):
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    cv = candidate()
    cv["education"] = [{"degree": "Bachelor's degree in Analytics", "completed": True}]
    monkeypatch.setattr(jobs, "load_cv_master", lambda: cv)
    with Session(engine) as db:
        imported = jobs.import_job(JobImport(title="Data Engineer", company="Example",
                                   location="Berlin, Germany", description="MSc required. SQL and Python required."), db)
        assert imported.created is True
        assert imported.job.qualification_assessment["recommendation"] == "unlikely"
        assert imported.job.match_score < 30
        stored = db.get(Job, imported.job.id)
        assert not hasattr(stored, "qualification_assessment")
        cv["education"] = [{"degree": "Master's degree in Analytics", "completed": True}]
        detail = jobs.get_job(stored.id, db)
        assert detail.qualification_assessment["recommendation"] == "strong"
        assert not hasattr(stored, "qualification_assessment") and stored.match_score < 30
    engine.dispose()

from types import SimpleNamespace
from unittest.mock import patch

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.db import Base
from app.models.job import ScoreCache
from app.schemas.job import ScoredJobResult
from app.scoring.scorer import score_job


def test_explicit_retry_replaces_heuristic_cache_then_reuses_valid_result():
    engine = create_engine('sqlite://')
    Base.metadata.create_all(engine)
    job = {'hash': 'recovery', 'title': 'Python Developer', 'description': 'Python APIs ' * 30}
    profile = {'skills': {'backend': ['Python']}}
    with Session(engine) as db, patch('app.scoring.scorer.constrain_score', side_effect=lambda result, *args, **kwargs: result):
        with patch('app.scoring.scorer.get_router', return_value=SimpleNamespace(available_providers=lambda tier: [])):
            first = score_job(db, job, profile)
            assert 'heuristic' in first.rejection_reason.lower()
        router = SimpleNamespace(available_providers=lambda tier: ['configured'])
        with patch('app.scoring.scorer.get_router', return_value=router), patch('app.scoring.scorer._call_router', return_value=ScoredJobResult(match_score=78)) as call:
            assert score_job(db, job, profile).match_score == first.match_score
            call.assert_not_called()
            assert score_job(db, job, profile, retry_heuristic=True).match_score == 78
            assert score_job(db, job, profile, retry_heuristic=True).match_score == 78
            call.assert_called_once()
        assert len(list(db.scalars(select(ScoreCache)))) == 1

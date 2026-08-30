"""Scorer de ofertas usando LLMRouter (tier=scoring) con cache local."""

from __future__ import annotations

import json
import logging
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.client import parse_json_block, run_sync
from app.ai.router import get_router
from app.models.job import ScoreCache
from app.schemas.job import ScoredJobResult, ScrapedJob
from app.scoring.prompts import build_scoring_system, build_scoring_user_prompt

logger = logging.getLogger(__name__)

CV_VERSION = "1"


def _heuristic_result(job: dict[str, Any], cv: dict[str, Any]) -> ScoredJobResult:
    """Fallback sin API: keyword overlap con skills del CV."""
    text = " ".join(
        [
            job.get("title", ""),
            job.get("description", "") or "",
            job.get("location", ""),
            " ".join(job.get("tags", []) or []),
        ]
    ).lower()

    all_skills = []
    for v in cv.get("skills", {}).values():
        if isinstance(v, list):
            all_skills.extend(v)
    all_skills = [s.lower() for s in all_skills]

    matches = [s for s in all_skills if s and s in text]
    score = min(95, 20 + len(matches) * 6)

    return ScoredJobResult(
        match_score=score,
        key_matches=matches[:6] or ["heuristic_fallback"],
        missing_skills=[],
        personalization_hooks=[],
        rejection_reason=None if score >= 30 else "low keyword overlap (heuristic)",
    )


def score_job(
    db: Session,
    job: ScrapedJob | dict[str, Any],
    cv_master: dict[str, Any],
) -> ScoredJobResult:
    """Puntua una oferta. Usa cache local si existe; si no, llama al router (tier=scoring).

    Si todos los providers fallan, fallback heuristico para no romper el pipeline.
    """
    job_dict: dict[str, Any] = job.model_dump() if isinstance(job, ScrapedJob) else dict(job)
    job_hash: str = job_dict.get("hash") or ""

    if job_hash:
        cached = db.execute(
            select(ScoreCache).where(
                ScoreCache.job_hash == job_hash, ScoreCache.cv_version == CV_VERSION
            )
        ).scalar_one_or_none()
        if cached is not None:
            try:
                return ScoredJobResult.model_validate(cached.result_json)
            except Exception:  # noqa: BLE001
                pass

    router = get_router()
    if not router.available_providers("scoring"):
        logger.warning("No hay providers LLM disponibles para scoring, fallback heuristico")
        result = _heuristic_result(job_dict, cv_master)
    else:
        result = _call_router(job_dict, cv_master)

    if job_hash:
        try:
            db.add(
                ScoreCache(
                    job_hash=job_hash,
                    cv_version=CV_VERSION,
                    result_json=result.model_dump(),
                )
            )
            db.commit()
        except Exception:  # noqa: BLE001
            db.rollback()

    return result


def _call_router(job: dict[str, Any], cv: dict[str, Any]) -> ScoredJobResult:
    router = get_router()
    try:
        user_prompt = (
            "Candidate CV (reference, identical across calls):\n"
            + json.dumps(cv, ensure_ascii=False)
            + "\n\n"
            + build_scoring_user_prompt({}, job)
        )
        response = run_sync(
            router.complete_for(
                tier="scoring",
                system=build_scoring_system(cv),
                user=user_prompt,
                max_tokens=800,
                temperature=0.2,
                json_mode=True,
            )
        )
        parsed = parse_json_block(response.content)
        return ScoredJobResult.model_validate(parsed)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Scoring via router fallido, usando heuristico: %s", exc)
        return _heuristic_result(job, cv)

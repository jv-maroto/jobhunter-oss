"""Scorer de ofertas usando LLMRouter (tier=scoring) con cache local."""

from __future__ import annotations

import hashlib
import json
import logging
import re
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.client import parse_json_block, run_sync
from app.ai.router import get_router
from app.models.job import ScoreCache
from app.schemas.job import ScoredJobResult, ScrapedJob
from app.scoring.compatibility import constrain_score
from app.scoring.prompts import _flatten_skills, build_scoring_system, build_scoring_user_prompt

logger = logging.getLogger(__name__)

SCORING_VERSION = "qualification-evidence-3"


def _heuristic_result(job: dict[str, Any], cv: dict[str, Any], *, assessment: dict[str, Any] | None = None) -> ScoredJobResult:
    """Fallback sin API: keyword overlap con skills del CV."""
    text = " ".join(
        [
            job.get("title", ""),
            job.get("description", "") or "",
        ]
    ).lower()

    all_skills = [skill.lower() for skill in _flatten_skills(cv)]
    matches = [s for s in all_skills if s and re.search(r"(?<!\w)" + re.escape(s) + r"(?!\w)", text)]
    from app.scoring.track_detector import detect_track

    roles = (cv.get("search_preferences") or {}).get("roles") or []
    role_match = any(detect_track(str(role)) == detect_track(job.get("title", "")) for role in roles)
    score = min(54, (40 if role_match else 20) + len(matches) * 6)

    incomplete = len(str(job.get("description") or "").strip()) < 80
    if incomplete:
        score = min(score, 54)

    result = constrain_score(ScoredJobResult(
        match_score=score,
        key_matches=matches[:6] or ["heuristic_fallback"],
        missing_skills=[],
        personalization_hooks=[],
        rejection_reason="Posting requirements are incomplete (heuristic)" if incomplete else (None if score >= 30 else "low keyword overlap (heuristic)"),
    ), job, cv, assessment=assessment)
    detail = result.rejection_reason
    result.rejection_reason = "Heuristic fit estimate (no AI evaluation)" + (f": {detail}" if detail else "")
    return result


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
    cv_version = hashlib.sha256(json.dumps(
        {"version": SCORING_VERSION, "cv": cv_master, "job": job_dict},
        sort_keys=True, ensure_ascii=False, default=str,
    ).encode()).hexdigest()[:32]

    if job_hash:
        cached = db.execute(
            select(ScoreCache).where(
                ScoreCache.job_hash == job_hash, ScoreCache.cv_version == cv_version
            )
        ).scalar_one_or_none()
        if cached is not None:
            try:
                return constrain_score(ScoredJobResult.model_validate(cached.result_json), job_dict, cv_master)
            except Exception:  # noqa: BLE001
                pass

    router = get_router()
    if not router.available_providers("scoring"):
        logger.warning("No hay providers LLM disponibles para scoring, fallback heuristico")
        result = _heuristic_result(job_dict, cv_master)
    else:
        result = _call_router(job_dict, cv_master)

    result = constrain_score(result, job_dict, cv_master)

    if job_hash:
        try:
            db.add(
                ScoreCache(
                    job_hash=job_hash,
                    cv_version=cv_version,
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
        # KEY OPTIMISATION: put the CV JSON into the SYSTEM prompt, not the
        # user prompt. The CV is identical across every scoring call, so
        # Anthropic's prompt caching (cache_control) can amortise it — the
        # second and subsequent calls within a 5-minute window pay ~10% of
        # the input tokens instead of 100%. Empirically this cuts scoring
        # cost by ~60% (the CV JSON is the bulk of the input).
        # anthropic_provider auto-enables cache_control once the system
        # crosses the Haiku threshold (2048 tokens) which the CV virtually
        # guarantees.
        system_prompt = (
            build_scoring_system(cv)
            + "\n\nCandidate CV (reference, identical across all scoring calls):\n"
            + json.dumps(cv, ensure_ascii=False)
        )
        user_prompt = build_scoring_user_prompt({}, job)
        response = run_sync(
            router.complete_for(
                tier="scoring",
                system=system_prompt,
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

"""Respuestas a preguntas de screening de formularios, con cache + IA.

Usa narratives + datos del cv_master. Degrada sin LLM (devuelve vacio). Siempre
en borrador: el usuario revisa antes de enviar.
"""

from __future__ import annotations

import hashlib
import json
import logging
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.client import complete
from app.ai.router import get_router
from app.models.answer_cache import AnswerCache
from app.models.job import Job
from app.services import load_cv_master

logger = logging.getLogger(__name__)

_SYSTEM = """Eres el candidato respondiendo una pregunta de un formulario de empleo.
Responde en primera persona, breve y honesto, usando SOLO la informacion del perfil
proporcionado (cv_master + narratives). Si te dan opciones, elige la mas adecuada y
devuelve EXACTAMENTE el texto de una de ellas. No inventes datos que no esten en el perfil."""


def _hash(question: str) -> str:
    return hashlib.md5(question.strip().lower().encode("utf-8")).hexdigest()


def _llm_available() -> bool:
    try:
        return bool(get_router().available_providers("messaging"))
    except Exception:  # noqa: BLE001
        return False


def answer_question(
    db: Session, job: Job, question: str, options: list[str] | None = None
) -> dict[str, Any]:
    question = (question or "").strip()
    if not question:
        return {"answer": "", "cached": False}

    qh = _hash(question + ("|" + "|".join(options) if options else ""))
    cached = db.execute(
        select(AnswerCache).where(AnswerCache.job_id == job.id, AnswerCache.question_hash == qh)
    ).scalar_one_or_none()
    if cached is not None:
        return {"answer": cached.answer, "cached": True}

    if not _llm_available():
        return {"answer": "", "cached": False}

    cv = load_cv_master() or {}
    profile = {
        "personal": cv.get("personal", {}),
        "summary": cv.get("summary_en") or cv.get("summary_es", ""),
        "skills": cv.get("skills", {}),
        "narratives": cv.get("narratives", {}),
        "search_preferences": {
            k: cv.get("search_preferences", {}).get(k)
            for k in ("salary_expectation", "notice_period", "work_authorization_eu", "willing_to_relocate")
        },
    }
    user = json.dumps(
        {
            "perfil": profile,
            "oferta": {"title": job.title, "company": job.company},
            "pregunta": question,
            "opciones": options or [],
        },
        ensure_ascii=False,
    )
    try:
        answer = complete(tier="messaging", system=_SYSTEM, user=user, max_tokens=400, temperature=0.3).strip()
    except Exception as exc:  # noqa: BLE001
        logger.warning("answer_question fallo: %s", exc)
        return {"answer": "", "cached": False}

    db.add(AnswerCache(job_id=job.id, question_hash=qh, question=question, answer=answer))
    db.commit()
    return {"answer": answer, "cached": False}

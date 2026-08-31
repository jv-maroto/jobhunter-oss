"""Endpoints para la extension browser de LinkedIn."""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.apply_queue import ApplyQueueItem
from app.models.job import Job
from app.models.person import Person
from app.models.post import Post

router = APIRouter(prefix="/ext", tags=["ext"])


@router.get("/profile")
def get_profile() -> dict:
    """Perfil estructurado del candidato para auto-relleno de formularios externos.

    Lo consume el content script de la extensión cuando detecta un form de aplicación
    en Wellfound, Lever, Greenhouse, Workable, Ashby, WTTJ, etc.
    """
    from app.services import load_cv_master

    cv = load_cv_master() or {}
    personal = cv.get("personal", {})
    name_full = personal.get("name", "")
    parts = name_full.split(" ")
    first = parts[0] if parts else ""
    last = " ".join(parts[-2:]) if len(parts) > 2 else (parts[-1] if len(parts) > 1 else "")

    # All narrative fields come from cv_master.json. Customise yours in
    # backend/app/data/cv_master.json (or via /settings page in the dashboard).
    prefs = cv.get("search_preferences", {}) or {}
    narratives = cv.get("narratives", {}) or {}
    education = cv.get("education") or []
    top_education = education[0] if education else {}
    return {
        "first_name": first,
        "last_name": last,
        "full_name": name_full,
        "email": personal.get("email", ""),
        "phone": personal.get("phone", ""),
        "linkedin_url": personal.get("linkedin", ""),
        "github_url": personal.get("github", ""),
        "portfolio_url": personal.get("portfolio", ""),
        "location": personal.get("location_short", ""),
        "city": personal.get("city", ""),
        "country": personal.get("country", ""),
        "academic_degree": (
            personal.get("academic_degree")
            or top_education.get("degree_en")
            or top_education.get("degree_es")
            or ""
        ),
        "graduation_date": (
            personal.get("graduation_date")
            or top_education.get("graduation_date")
            or top_education.get("year", "")
        ),
        "current_role": cv.get("experience", [{}])[0].get("role", "") if cv.get("experience") else "",
        "current_company": cv.get("experience", [{}])[0].get("company", "") if cv.get("experience") else "",
        "years_experience": str(cv.get("years_experience", "")),
        "salary_min_eur": prefs.get("salary_min_eur", 30000),
        "salary_max_eur": prefs.get("salary_max_eur", 50000),
        "salary_expectation": prefs.get("salary_expectation", ""),
        "work_authorization_eu": prefs.get("work_authorization_eu", False),
        "residence_country": prefs.get("residence_country") or personal.get("country", ""),
        "willing_to_relocate": prefs.get("willing_to_relocate", True),
        "remote_preference": prefs.get("remote_preference", "Open to remote"),
        "notice_period": prefs.get("notice_period", "2 weeks"),
        "languages": prefs.get("languages_text", ""),
        "summary": cv.get("summary_en") or cv.get("summary_es") or "",
        # Long-form narratives — define in cv_master.json under "narratives":
        #   { "experience": "...", "frontend_showcase": "...", "backend_showcase": "...",
        #     "production_system_story": "...", "cover_letter": "..." }
        "experience_narrative": narratives.get("experience", cv.get("summary_en", "")),
        "frontend_showcase": narratives.get("frontend_showcase", ""),
        "backend_showcase": narratives.get("backend_showcase", ""),
        "production_system_story": narratives.get("production_system_story", ""),
        "cover_letter_generic": narratives.get("cover_letter", ""),
    }


class ConnectPersonTask(BaseModel):
    id: str
    type: str = "connect_person"
    person_id: int
    profile_url: str
    message: str
    priority: int | None = None


class SchedulePostTask(BaseModel):
    id: str
    type: str = "schedule_post"
    post_id: int
    content: str
    scheduled_at: str
    image_url: str | None = None
    hashtags: list[str] = []


class ReadInboxTask(BaseModel):
    id: str
    type: str = "read_inbox"


class ExtTasksResponse(BaseModel):
    tasks: list[dict]


class ConnectResultIn(BaseModel):
    task_id: str | None = None
    person_id: int
    success: bool
    error: str | None = None
    executed_at: datetime | None = None


class InboxMessageIn(BaseModel):
    sender_url: str | None = None
    sender_name: str
    body: str | None = None
    preview: str | None = None
    received_at: datetime | None = None
    unread: bool | None = None
    thread_id: str | None = None


class PostResultIn(BaseModel):
    task_id: str | None = None
    post_id: int
    success: bool
    error: str | None = None
    scheduled_at: datetime | None = None


@router.get("/tasks", response_model=ExtTasksResponse)
def get_tasks(limit: int = 5, db: Session = Depends(get_db)) -> ExtTasksResponse:
    """Devuelve siguientes tareas que la extension debe ejecutar en LinkedIn."""
    tasks: list[dict] = []

    # 1) Conexiones pendientes (prioridad alta)
    pending_people = db.execute(
        select(Person)
        .where(Person.status.in_(["pending", "queued"]))
        .order_by(desc(Person.priority))
        .limit(limit)
    ).scalars().all()
    for p in pending_people:
        tasks.append({
            "id": f"connect-{p.id}",
            "type": "connect_person",
            "person_id": p.id,
            "profile_url": p.profile_url,
            "message": p.message or "",
            "priority": p.priority,
        })

    # 2) Posts programados pendientes de empujar a LinkedIn scheduler
    now = datetime.utcnow()
    pending_posts = db.execute(
        select(Post)
        .where(
            Post.status == "scheduled",
            Post.scheduled_at != None,  # noqa: E711
            Post.scheduled_at > now,
        )
        .order_by(Post.scheduled_at)
        .limit(3)
    ).scalars().all()
    for post in pending_posts:
        tasks.append({
            "id": f"post-{post.id}",
            "type": "schedule_post",
            "post_id": post.id,
            "content": post.content,
            "scheduled_at": post.scheduled_at.isoformat() if post.scheduled_at else "",
            "image_url": None,
            "hashtags": post.hashtags or [],
        })

    # 3) Inbox scan (siempre)
    tasks.append({"id": "inbox-latest", "type": "read_inbox"})

    return ExtTasksResponse(tasks=tasks)


@router.post("/post-result")
def post_result(payload: PostResultIn, db: Session = Depends(get_db)) -> dict:
    """La extension reporta el resultado de programar un post en LinkedIn."""
    post = db.get(Post, payload.post_id)
    if post is None:
        raise HTTPException(status_code=404, detail="Post not found")
    if payload.success:
        post.status = "published"
        post.published_at = datetime.utcnow()
        if payload.scheduled_at is not None:
            post.scheduled_at = payload.scheduled_at
    else:
        prefix = post.content or ""
        post.content = f"{prefix}\n[ext-error] {payload.error or 'unknown'}"
    db.commit()
    return {"ok": True, "post_id": post.id, "status": post.status}


@router.post("/connect-result")
def connect_result(payload: ConnectResultIn, db: Session = Depends(get_db)) -> dict:
    p = db.get(Person, payload.person_id)
    if not p:
        raise HTTPException(status_code=404, detail="Person not found")
    if payload.success:
        p.status = "sent"
        p.sent_at = datetime.utcnow()
    else:
        p.status = "ignored"
        p.notes = (p.notes or "") + f"\n[ext-error]{payload.error or ''}"
    db.commit()
    return {"ok": True, "person_id": p.id, "status": p.status}


@router.post("/inbox-messages")
def inbox_messages(payload: list[InboxMessageIn], db: Session = Depends(get_db)) -> dict:
    """Recibe mensajes inbox de la extension. Notas en Person si existe."""
    matched = 0
    for msg in payload:
        if not msg.sender_url:
            continue
        p = db.execute(
            select(Person).where(Person.profile_url == msg.sender_url)
        ).scalar_one_or_none()
        if p is None:
            continue
        snippet = (msg.preview or msg.body or "")[:500]
        p.notes = (p.notes or "") + (
            f"\n[inbox {msg.received_at or datetime.utcnow()}] {snippet}"
        )
        if p.status == "sent":
            p.status = "accepted"
            p.accepted_at = datetime.utcnow()
        matched += 1
    db.commit()
    return {"received": len(payload), "matched": matched}




# ---------------- Aplicar (Pilar 3): cola + reporte + screening ----------------


@router.get("/apply-queue")
def apply_queue(limit: int = 5, db: Session = Depends(get_db)) -> dict:
    """Ofertas en cola para que la extension rellene/aplique (status=queued)."""
    items = db.execute(
        select(ApplyQueueItem)
        .where(ApplyQueueItem.status == "queued")
        .order_by(ApplyQueueItem.created_at)
        .limit(limit)
    ).scalars().all()
    out = []
    for it in items:
        job = db.get(Job, it.job_id)
        out.append({
            "queue_id": it.id,
            "job_id": it.job_id,
            "platform": it.platform,
            "apply_url": it.apply_url,
            "materials": it.materials or {},
            "title": job.title if job else "",
            "company": job.company if job else "",
        })
    return {"tasks": out}


class AppliedIn(BaseModel):
    job_id: int
    platform: str = ""
    apply_url: str = ""
    status: str = "submitted"
    queue_id: int | None = None
    screening_answers: dict | None = None


@router.post("/applied")
def report_applied(payload: AppliedIn, db: Session = Depends(get_db)) -> dict:
    """La extension reporta que una oferta se envio -> avanza el pipeline a 'applied'."""
    from app.apply.orchestrator import record_applied

    job = db.get(Job, payload.job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job no encontrado")
    app_row = record_applied(
        db, job,
        platform=payload.platform,
        apply_url=payload.apply_url,
        screening_answers=payload.screening_answers,
        queue_id=payload.queue_id,
    )
    return {"ok": True, "job_id": job.id, "job_status": job.status, "application_id": app_row.id}


class AnswerQuestionIn(BaseModel):
    job_id: int
    question: str
    options: list[str] | None = None


@router.post("/answer-question")
def answer_question_ep(payload: AnswerQuestionIn, db: Session = Depends(get_db)) -> dict:
    """Sugiere (en borrador) una respuesta a una pregunta de screening del formulario."""
    from app.apply.screening import answer_question

    job = db.get(Job, payload.job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job no encontrado")
    return answer_question(db, job, payload.question, payload.options)

"""Endpoints de posts LinkedIn."""

from __future__ import annotations

import logging
from datetime import date as date_t
from datetime import datetime, timedelta
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.ai.image_generator import generate_post_image as generate_post_image_pillow
from app.ai.image_generator_html import generate_post_image_html
from app.ai.post_generator import generate_trending_posts, generate_weekly_posts
from app.scrapers.article_summary import fetch_summaries
from app.scrapers.hacker_news import fetch_top_hn_24h


def generate_post_image(post_id: int, post_data: dict) -> Path | None:
    """Try HTML+Playwright (infographic style) first, then Pillow fallback.

    Pollinations.ai generates AI illustrations (penguin-style) which do NOT
    match the user's requested aesthetic (composite infographic with code +
    bullets + mockups). Only kept as last-resort.
    """
    p = generate_post_image_html(post_id, post_data)
    if p is not None:
        return p
    logger.warning("HTML render failed for post %s, falling back to Pillow", post_id)
    return generate_post_image_pillow(post_id, post_data)

logger = logging.getLogger(__name__)
from app.db import get_db
from app.models.post import Post
from app.schemas.post import PostGenerateIn, PostOut, PostPatch, TrendingGenerateIn
from app.services import load_cv_master

router = APIRouter(prefix="/posts", tags=["posts"])


@router.get("", response_model=list[PostOut])
def list_posts(
    status: str | None = Query(default=None),
    date: date_t | None = Query(default=None),
    db: Session = Depends(get_db),
) -> list[PostOut]:
    stmt = select(Post).order_by(desc(Post.date), desc(Post.created_at))
    if status:
        stmt = stmt.where(Post.status == status)
    if date is not None:
        stmt = stmt.where(Post.date == date)
    return [PostOut.model_validate(p) for p in db.execute(stmt).scalars().all()]


# ---------------------------------------------------------------------------
# Status endpoints — declared BEFORE /{post_id} to avoid path clash.
# ---------------------------------------------------------------------------
@router.get("/generate-week-status")
def generate_week_status_early() -> dict:
    """Status of background generate-week task."""
    return dict(_GENWEEK_STATE)


@router.get("/generate-trending-status")
def generate_trending_status_early() -> dict:
    """Status of background generate-trending task."""
    return dict(_TRENDING_STATE)


@router.get("/{post_id}", response_model=PostOut)
def get_post(post_id: int, db: Session = Depends(get_db)) -> PostOut:
    p = db.get(Post, post_id)
    if not p:
        raise HTTPException(status_code=404, detail="Post not found")
    return PostOut.model_validate(p)


@router.patch("/{post_id}", response_model=PostOut)
def patch_post(post_id: int, patch: PostPatch, db: Session = Depends(get_db)) -> PostOut:
    p = db.get(Post, post_id)
    if not p:
        raise HTTPException(status_code=404, detail="Post not found")
    if patch.status:
        p.status = patch.status
        if patch.status == "published" and not p.published_at:
            p.published_at = datetime.utcnow()
    if patch.scheduled_at is not None:
        p.scheduled_at = patch.scheduled_at
    if patch.content is not None:
        p.content = patch.content
    db.commit()
    db.refresh(p)
    return PostOut.model_validate(p)


class SchedulePostIn(BaseModel):
    when: datetime | None = None


@router.post("/{post_id}/schedule", response_model=PostOut)
def schedule_post(
    post_id: int,
    payload: SchedulePostIn | None = None,
    db: Session = Depends(get_db),
) -> PostOut:
    """Marca un post como `scheduled` y crea efectivamente una tarea
    `schedule_post` para que la extension Chrome la programe en LinkedIn.

    Si no se pasa `when`, se programa para mañana a las 09:00 (hora del servidor).
    """
    p = db.get(Post, post_id)
    if not p:
        raise HTTPException(status_code=404, detail="Post not found")

    when = payload.when if payload else None
    if when is None:
        when = (datetime.utcnow() + timedelta(days=1)).replace(
            hour=9, minute=0, second=0, microsecond=0
        )

    p.status = "scheduled"
    p.scheduled_at = when
    p.date = when.date()
    db.commit()
    db.refresh(p)
    return PostOut.model_validate(p)


@router.post("/{post_id}/generate-image", response_model=PostOut)
def generate_image(post_id: int, db: Session = Depends(get_db)) -> PostOut:
    """Generate (or regenerate) the visual for a post using Playwright."""
    p = db.get(Post, post_id)
    if not p:
        raise HTTPException(status_code=404, detail="Post not found")
    img_path = generate_post_image(
        p.id,
        {
            "topic": p.topic,
            "content": p.content,
            "category": (p.content[:40] if p.content else "project"),
            "hashtags": p.hashtags or [],
        },
    )
    if img_path is None:
        raise HTTPException(
            status_code=500,
            detail="Failed to generate image (Playwright not available?)",
        )
    p.image_path = str(img_path)
    db.commit()
    db.refresh(p)
    return PostOut.model_validate(p)


@router.get("/{post_id}/image")
def get_post_image(post_id: int, download: bool = False, db: Session = Depends(get_db)):
    p = db.get(Post, post_id)
    if not p or not p.image_path:
        raise HTTPException(status_code=404, detail="Post has no image yet")
    path = Path(p.image_path)
    if not path.exists():
        raise HTTPException(status_code=410, detail="Image file missing on disk")
    headers = {}
    if download:
        import re as _re
        topic = (p.topic or f"post-{post_id}").lower()
        slug = _re.sub(r"[^a-z0-9]+", "-", topic).strip("-")[:60] or f"post-{post_id}"
        headers["Content-Disposition"] = f'attachment; filename="jobhunter-{slug}.png"'
    return FileResponse(path, media_type="image/png", headers=headers)


# ---------------------------------------------------------------------------
# Generate-week as a background task (LLM + image generation can take 1-3 min)
# ---------------------------------------------------------------------------

_GENWEEK_STATE: dict[str, object] = {
    "running": False,
    "started_at": None,
    "finished_at": None,
    "requested": 0,
    "created": 0,
    "images_done": 0,
    "error": None,
}


def _run_generate_week(theme: str, count: int, language: str) -> None:
    """Runs the LLM + image generation. Uses a fresh DB session."""
    from app.ai.post_generator import NoLLMAvailableError
    from app.db import SessionLocal

    _GENWEEK_STATE["running"] = True
    _GENWEEK_STATE["started_at"] = datetime.utcnow().isoformat()
    _GENWEEK_STATE["finished_at"] = None
    _GENWEEK_STATE["requested"] = count
    _GENWEEK_STATE["created"] = 0
    _GENWEEK_STATE["images_done"] = 0
    _GENWEEK_STATE["error"] = None

    db = SessionLocal()
    try:
        cv = load_cv_master()
        existing_topics = [
            t for (t,) in db.execute(
                select(Post.topic).order_by(desc(Post.created_at)).limit(60)
            ).all()
            if t
        ]

        items = generate_weekly_posts(
            cv, theme=theme, count=count, language=language, avoid_topics=existing_topics
        )

        today = date_t.today()
        posts_per_day = max(1, count // 7) if count >= 7 else 1

        out: list[Post] = []
        for i, p in enumerate(items):
            day_offset = i // posts_per_day
            post = Post(
                date=today + timedelta(days=day_offset),
                topic=str(p.get("topic", "Untitled")),
                content=str(p.get("content", "")),
                hashtags=list(p.get("hashtags", []) or []),
                image_prompt=p.get("image_prompt"),
                status="draft",
            )
            db.add(post)
            out.append(post)
        db.commit()
        _GENWEEK_STATE["created"] = len(out)

        for p, item in zip(out, items, strict=False):
            db.refresh(p)
            try:
                img_path = generate_post_image(
                    p.id,
                    {
                        "topic": p.topic,
                        "content": p.content,
                        "category": str(item.get("category", "project")),
                        "hashtags": p.hashtags or [],
                    },
                )
                if img_path is not None:
                    p.image_path = str(img_path)
                    db.commit()
                    _GENWEEK_STATE["images_done"] = (
                        int(_GENWEEK_STATE["images_done"]) + 1
                    )
            except Exception as e:  # noqa: BLE001
                logger.warning("image gen failed for post %s: %s", p.id, e)
                db.rollback()
    except NoLLMAvailableError as exc:
        _GENWEEK_STATE["error"] = str(exc)[:200]
        logger.warning("generate-week LLM not available: %s", exc)
    except Exception as exc:  # noqa: BLE001
        _GENWEEK_STATE["error"] = str(exc)[:200]
        logger.exception("generate-week failed: %s", exc)
    finally:
        db.close()
        _GENWEEK_STATE["running"] = False
        _GENWEEK_STATE["finished_at"] = datetime.utcnow().isoformat()


@router.post("/generate-week")
def generate_week(payload: PostGenerateIn, background_tasks: BackgroundTasks) -> dict:
    """Dispara generación de la semana en background. Devuelve inmediatamente.
    Frontend hace polling a /posts/generate-week-status para ver progreso."""
    if _GENWEEK_STATE.get("running"):
        return {"status": "already_running", **_GENWEEK_STATE}
    background_tasks.add_task(
        _run_generate_week, payload.theme, payload.count, payload.language
    )
    return {"status": "started", "requested": payload.count}


# (status endpoint declared above /{post_id} to avoid path clash)


# ---------------------------------------------------------------------------
# Trending posts (Hacker News last 24h → Claude → posts + news-template imgs)
# ---------------------------------------------------------------------------

_TRENDING_STATE: dict[str, object] = {
    "running": False,
    "started_at": None,
    "finished_at": None,
    "requested": 0,
    "stories_found": 0,
    "created": 0,
    "images_done": 0,
    "error": None,
}


def _run_generate_trending(count: int, language: str, replace_drafts: bool) -> None:
    """Fetch HN top stories, generate trending posts + news-template images."""
    import asyncio
    from app.ai.post_generator import NoLLMAvailableError
    from app.db import SessionLocal

    _TRENDING_STATE.update({
        "running": True,
        "started_at": datetime.utcnow().isoformat(),
        "finished_at": None,
        "requested": count,
        "stories_found": 0,
        "created": 0,
        "images_done": 0,
        "error": None,
    })

    db = SessionLocal()
    try:
        # 1) Fetch HN
        try:
            stories = asyncio.run(fetch_top_hn_24h(limit=count))
        except RuntimeError:
            # If we're inside an async loop already, run in a new thread
            import threading
            holder: dict = {}
            def runner():
                holder["v"] = asyncio.run(fetch_top_hn_24h(limit=count))
            t = threading.Thread(target=runner)
            t.start()
            t.join()
            stories = holder.get("v", [])
        _TRENDING_STATE["stories_found"] = len(stories)
        if not stories:
            _TRENDING_STATE["error"] = "No stories found in last 24h"
            return

        # 1.5) Fetch og:description from each article URL in parallel
        try:
            summaries = asyncio.run(
                fetch_summaries([s["url"] for s in stories])
            )
        except RuntimeError:
            import threading
            sholder: dict = {}
            def srunner():
                sholder["v"] = asyncio.run(
                    fetch_summaries([s["url"] for s in stories])
                )
            t2 = threading.Thread(target=srunner)
            t2.start()
            t2.join()
            summaries = sholder.get("v", {})
        for s in stories:
            s["summary"] = summaries.get(s["url"], "")

        # 2) Optionally clear existing draft trending posts
        if replace_drafts:
            old = db.execute(
                select(Post).where(Post.kind == "trending", Post.status == "draft")
            ).scalars().all()
            for p in old:
                if p.image_path:
                    try:
                        Path(p.image_path).unlink(missing_ok=True)
                    except Exception:  # noqa: BLE001
                        pass
                db.delete(p)
            db.commit()

        # 3) Generate post text via Claude
        cv = load_cv_master()
        items = generate_trending_posts(stories, cv, language=language)

        # 4) Persist posts + generate images with news template
        today = date_t.today()
        out: list[Post] = []
        for i, item in enumerate(items):
            # Pair each generated post with its source story by index (Claude
            # is asked to preserve order). Fallback to first story if missing.
            story = stories[i] if i < len(stories) else stories[0]
            source_url = str(item.get("source_url") or story.get("url") or "").strip()
            # Ensure the source URL is at the end of the content so readers can click
            content_with_link = str(item.get("content", "")).rstrip()
            if source_url and source_url not in content_with_link:
                content_with_link = f"{content_with_link}\n\n🔗 Fuente: {source_url}"
            post = Post(
                date=today + timedelta(days=i),
                topic=str(item.get("topic", "Untitled")),
                content=content_with_link,
                hashtags=list(item.get("hashtags", []) or []),
                image_prompt=item.get("image_prompt"),
                status="draft",
                kind="trending",
                source_url=source_url,
                source_summary=str(story.get("summary") or "")[:500] or None,
            )
            db.add(post)
            out.append(post)
        db.commit()
        _TRENDING_STATE["created"] = len(out)

        for idx, (p, item) in enumerate(zip(out, items, strict=False)):
            db.refresh(p)
            # Pair with original HN story for metadata
            story = stories[idx] if idx < len(stories) else {}
            try:
                img_path = generate_post_image(
                    p.id,
                    {
                        "topic": p.topic,
                        "content": p.content,
                        "category": str(item.get("category", "project")),
                        "kind": "trending",
                        "source_url": p.source_url or "",
                        "source_summary": p.source_summary or "",
                        "original_title": str(story.get("title", "")),
                        "hn_score": int(story.get("score", 0) or 0),
                        "hn_comments": int(story.get("comments", 0) or 0),
                        "hashtags": p.hashtags or [],
                    },
                )
                if img_path is not None:
                    p.image_path = str(img_path)
                    db.commit()
                    _TRENDING_STATE["images_done"] = (
                        int(_TRENDING_STATE["images_done"]) + 1
                    )
            except Exception as e:  # noqa: BLE001
                logger.warning("trending image gen failed for post %s: %s", p.id, e)
                db.rollback()
    except NoLLMAvailableError as exc:
        _TRENDING_STATE["error"] = str(exc)[:200]
        logger.warning("generate-trending LLM not available: %s", exc)
    except Exception as exc:  # noqa: BLE001
        _TRENDING_STATE["error"] = str(exc)[:200]
        logger.exception("generate-trending failed: %s", exc)
    finally:
        db.close()
        _TRENDING_STATE["running"] = False
        _TRENDING_STATE["finished_at"] = datetime.utcnow().isoformat()


@router.post("/generate-trending")
def generate_trending(
    payload: TrendingGenerateIn, background_tasks: BackgroundTasks
) -> dict:
    """Dispara en background: fetch HN → Claude → posts trending + imágenes."""
    if _TRENDING_STATE.get("running"):
        return {"status": "already_running", **_TRENDING_STATE}
    background_tasks.add_task(
        _run_generate_trending, payload.count, payload.language, payload.replace_drafts
    )
    return {"status": "started", "requested": payload.count}

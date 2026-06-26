"""Endpoints de sugerencias de comentarios LinkedIn."""

from __future__ import annotations

import logging
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.ai.comment_generator import generate_comment
from app.db import get_db
from app.models.feed_post import FeedPost
from app.services import load_cv_master

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/comments", tags=["comments"])


class FeedPostIn(BaseModel):
    post_url: str
    author_name: str | None = None
    author_headline: str | None = None
    author_url: str | None = None
    content_excerpt: str | None = None
    language: str | None = None


class FeedPostBatchIn(BaseModel):
    posts: list[FeedPostIn] = Field(default_factory=list)


class CommentSuggestionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    post_url: str
    author_name: str | None = None
    author_headline: str | None = None
    content_excerpt: str | None = None
    suggested_comment: str | None = None
    relevance_score: float = 0.0
    language: str | None = None
    status: str
    captured_at: datetime


def _ensure_suggestion(post: FeedPost) -> None:
    """Genera comment con Claude si aún no hay uno."""
    if post.suggested_comment:
        return
    if not post.author_name or not post.content_excerpt:
        return
    cv = load_cv_master()
    comment, score = generate_comment(
        cv,
        author_name=post.author_name,
        author_headline=post.author_headline or "",
        content=post.content_excerpt,
    )
    post.suggested_comment = comment if comment else None
    post.relevance_score = score
    if comment:
        post.status = "suggested"


@router.get("/suggestions", response_model=list[CommentSuggestionOut])
def list_suggestions(
    limit: int = Query(default=10, ge=1, le=50),
    status: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> list[CommentSuggestionOut]:
    """Devuelve los posts del feed con comentario sugerido, ordenados por relevancia."""
    stmt = (
        select(FeedPost)
        .order_by(desc(FeedPost.relevance_score), desc(FeedPost.captured_at))
        .limit(limit * 3)
    )
    if status:
        stmt = stmt.where(FeedPost.status == status)
    candidates = db.execute(stmt).scalars().all()

    out: list[CommentSuggestionOut] = []
    for post in candidates:
        if not post.suggested_comment and post.author_name and post.content_excerpt:
            try:
                _ensure_suggestion(post)
                db.commit()
                db.refresh(post)
            except Exception as e:  # noqa: BLE001
                logger.warning("auto-suggestion failed for %s: %s", post.id, e)
                db.rollback()
        if post.suggested_comment:
            out.append(CommentSuggestionOut.model_validate(post))
        if len(out) >= limit:
            break
    return out


@router.post("/regenerate/{post_id}", response_model=CommentSuggestionOut)
def regenerate(post_id: int, db: Session = Depends(get_db)) -> CommentSuggestionOut:
    post = db.get(FeedPost, post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Feed post not found")
    if not post.author_name or not post.content_excerpt:
        raise HTTPException(status_code=400, detail="Post missing author or content")
    cv = load_cv_master()
    comment, score = generate_comment(
        cv,
        author_name=post.author_name,
        author_headline=post.author_headline or "",
        content=post.content_excerpt,
    )
    post.suggested_comment = comment if comment else None
    post.relevance_score = score
    if comment:
        post.status = "suggested"
    db.commit()
    db.refresh(post)
    return CommentSuggestionOut.model_validate(post)


@router.post("/mark-commented/{post_id}", response_model=CommentSuggestionOut)
def mark_commented(post_id: int, db: Session = Depends(get_db)) -> CommentSuggestionOut:
    post = db.get(FeedPost, post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Feed post not found")
    post.status = "commented"
    post.commented_at = datetime.utcnow()
    db.commit()
    db.refresh(post)
    return CommentSuggestionOut.model_validate(post)


@router.post("/skip/{post_id}", response_model=CommentSuggestionOut)
def skip(post_id: int, db: Session = Depends(get_db)) -> CommentSuggestionOut:
    post = db.get(FeedPost, post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Feed post not found")
    post.status = "skipped"
    db.commit()
    db.refresh(post)
    return CommentSuggestionOut.model_validate(post)


@router.post("/feed-posts", response_model=dict)
def ingest_feed_posts(payload: FeedPostBatchIn, db: Session = Depends(get_db)) -> dict:
    """La extensión envía posts del feed capturados."""
    inserted = 0
    dupes = 0
    for p in payload.posts:
        if not p.post_url:
            continue
        existing = db.execute(
            select(FeedPost).where(FeedPost.post_url == p.post_url)
        ).scalar_one_or_none()
        if existing is not None:
            dupes += 1
            continue
        row = FeedPost(
            post_url=p.post_url,
            author_name=p.author_name,
            author_headline=p.author_headline,
            author_url=p.author_url,
            content_excerpt=p.content_excerpt,
            language=p.language,
            status="new",
        )
        db.add(row)
        try:
            db.commit()
            inserted += 1
        except Exception as e:  # noqa: BLE001
            logger.warning("feed-post insert failed for %s: %s", p.post_url, e)
            db.rollback()
    return {"received": len(payload.posts), "inserted": inserted, "duplicates": dupes}


class ManualPostIn(BaseModel):
    post_url: str
    author_name: str | None = "Unknown"
    author_headline: str | None = None
    content_excerpt: str
    language: str | None = "en"


@router.post("/manual-post", response_model=CommentSuggestionOut)
def add_manual_post(payload: ManualPostIn, db: Session = Depends(get_db)) -> CommentSuggestionOut:
    """Añade manualmente un post de LinkedIn pegando URL + contenido.

    Para cuando la extensión no puede scrapear (browsers con restricciones,
    LinkedIn blindado, etc.). Genera el comentario sugerido inmediatamente.
    """
    if not payload.post_url or not payload.content_excerpt:
        raise HTTPException(status_code=400, detail="URL y contenido son obligatorios")

    existing = db.execute(
        select(FeedPost).where(FeedPost.post_url == payload.post_url)
    ).scalar_one_or_none()
    if existing is not None:
        # Update content if user provided new
        existing.content_excerpt = payload.content_excerpt
        existing.author_name = payload.author_name or existing.author_name
        existing.author_headline = payload.author_headline or existing.author_headline
        existing.language = payload.language or existing.language
        existing.suggested_comment = None  # regenerate
        post = existing
    else:
        post = FeedPost(
            post_url=payload.post_url,
            author_name=payload.author_name or "Unknown",
            author_headline=payload.author_headline,
            content_excerpt=payload.content_excerpt,
            language=payload.language or "en",
            status="new",
        )
        db.add(post)
    db.commit()
    db.refresh(post)

    _ensure_suggestion(post)
    db.commit()
    db.refresh(post)
    return CommentSuggestionOut.model_validate(post)

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.api import posts
from app.db import Base
from app.models.post import Post


def add(db, kind="trending", status="draft", days=10):
    row = Post(topic="News", content="Original draft", kind=kind, status=status,
               created_at=datetime.utcnow() - timedelta(days=days))
    db.add(row)
    db.commit()
    return row.id


def test_delete_old_news_preserves_recent_scheduled_published_and_personal():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        old = add(db)
        keep = {add(db, days=1), add(db, status="scheduled"),
                add(db, status="published"), add(db, kind="personal")}
        with patch("app.profile_store.atomic_write_json") as backup:
            assert posts.delete_old_trending(days=7, db=db) == {"deleted": 1, "days": 7}
            assert backup.call_args.args[1]["posts"][0]["id"] == old
        assert set(db.scalars(select(Post.id))) == keep
        assert posts.delete_old_trending(days=7, db=db)["deleted"] == 0


def test_delete_cannot_overlap_generation():
    posts._TRENDING_LOCK.acquire()
    try:
        with pytest.raises(HTTPException) as error:
            posts.delete_old_trending(days=7, db=None)
        assert error.value.status_code == 409
    finally:
        posts._TRENDING_LOCK.release()


@pytest.mark.parametrize("generated", [[], RuntimeError("Provider unavailable")])
def test_failed_regeneration_preserves_drafts(generated):
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        old = add(db)
    fake_generate = {"side_effect": generated} if isinstance(generated, Exception) else {"return_value": generated}
    with patch("app.db.SessionLocal", side_effect=lambda: Session(engine)), \
         patch.object(posts, "fetch_top_trending_24h", new=AsyncMock(return_value=[{"url": "https://example.com/news"}])), \
         patch.object(posts, "fetch_metas", new=AsyncMock(return_value={})), \
         patch.object(posts, "load_cv_master", return_value={}), \
         patch.object(posts, "generate_trending_posts", **fake_generate):
        posts._run_generate_trending(10, "es", True)
    with Session(engine) as db:
        assert db.get(Post, old).content == "Original draft"
    assert posts._TRENDING_STATE["error"]
    assert posts._TRENDING_STATE["running"] is False


def test_generation_skips_published_sources_and_keeps_rss_summary():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        old = add(db, status="published")
        db.get(Post, old).source_url = "https://example.com/old"
        db.commit()
    stories = [
        {"url": "https://example.com/old?utm_source=rss", "title": "Already published"},
        {"url": "https://example.com/new", "title": "New", "summary_raw": "RSS evidence"},
    ]
    with patch("app.db.SessionLocal", side_effect=lambda: Session(engine)), \
         patch.object(posts, "fetch_top_trending_24h", new=AsyncMock(return_value=stories)), \
         patch.object(posts, "fetch_metas", new=AsyncMock(return_value={})), \
         patch.object(posts, "load_cv_master", return_value={}), \
         patch.object(posts, "generate_trending_posts", return_value=[]) as generate:
        posts._run_generate_trending(15, "es", True)
    supplied = generate.call_args.args[0]
    assert [story["url"] for story in supplied] == ["https://example.com/new"]
    assert supplied[0]["summary"] == "RSS evidence"
    assert generate.call_args.kwargs["count"] == 15
    with Session(engine) as db:
        assert db.get(Post, old).status == "published"


def test_regeneration_preserves_edited_draft_and_excludes_its_source():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        edited = add(db)
        untouched = add(db)
        row = db.get(Post, edited)
        row.user_edited = True
        row.source_url = "https://example.com/edited"
        db.commit()
    stories = [
        {"url": "https://example.com/edited", "title": "Edited"},
        {"url": "https://example.com/new", "title": "New"},
    ]
    with patch("app.db.SessionLocal", side_effect=lambda: Session(engine)), \
         patch.object(posts, "fetch_top_trending_24h", new=AsyncMock(return_value=stories)), \
         patch.object(posts, "fetch_metas", new=AsyncMock(return_value={})), \
         patch.object(posts, "load_cv_master", return_value={}), \
         patch.object(posts, "generate_post_image", return_value=None), \
         patch.object(posts, "generate_trending_posts", return_value=[{
             "topic": "New", "content": "New evidence", "source_url": "https://example.com/new",
         }]) as generate:
        posts._run_generate_trending(1, "es", True)
    assert [story["url"] for story in generate.call_args.args[0]] == ["https://example.com/new"]
    with Session(engine) as db:
        assert db.get(Post, edited).content == "Original draft"
        assert db.get(Post, untouched) is None
        assert len(list(db.scalars(select(Post)))) == 2

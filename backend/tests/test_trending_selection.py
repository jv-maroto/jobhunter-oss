import time
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from app.ai.post_generator import generate_trending_posts
from app.scrapers.trending_sources import canonical_story_url, dedupe_and_rank


def story(url, title="Python developers release useful open source tools", **kwargs):
    return {"url": url, "title": title, "score": 100, "comments": 5,
            "time": int(time.time()), "by": "hn", **kwargs}


def test_tracking_and_cross_source_aliases_do_not_repeat_articles():
    stories = [
        story("https://example.com/a?utm_source=hn", by="hn"),
        story("https://example.com/b", by="techmeme", score=500),
        story("https://example.com/a", title="An alternative headline", by="reddit"),
    ]
    result = dedupe_and_rank(stories)
    assert len(result) == 1
    assert result[0]["_coverage"] == 3
    assert "_coverage" not in stories[0]


def test_same_source_repeats_do_not_inflate_coverage():
    result = dedupe_and_rank([story("https://example.com/a")] * 4)
    assert result[0]["_coverage"] == 1
    assert canonical_story_url("https://example.com/a?id=1&utm_source=x#top") == "https://example.com/a?id=1"


def test_rss_synthetic_votes_do_not_override_relevance():
    result = dedupe_and_rank([
        story("https://example.com/a", "Celebrity wedding pictures from yesterday", by="techmeme", score=50000),
        story("https://example.com/b", "Python developer security API release", by="hn", score=50),
    ])
    assert result[0]["url"].endswith("/b")


def test_generation_respects_count_and_only_accepts_supplied_distinct_sources():
    response = SimpleNamespace(content='''{"posts": [
      {"topic":"First", "content":"Valid", "source_url":"https://example.com/a"},
      {"topic":"Duplicate", "content":"Duplicate", "source_url":"https://example.com/a?utm_source=x"},
      {"topic":"Invented", "content":"Bad", "source_url":"https://invented.com/x"}
    ]}''')
    router = SimpleNamespace(available_providers=lambda _: ["test"],
                             complete_for=AsyncMock(return_value=response))
    with patch("app.ai.post_generator.get_router", return_value=router):
        result = generate_trending_posts([story("https://example.com/a")], {}, count=2)
    assert len(result) == 1
    assert result[0]["topic"] == "First"
    assert "count=2" in router.complete_for.call_args.kwargs["user"]
    assert router.complete_for.call_args.kwargs["max_tokens"] == 2500

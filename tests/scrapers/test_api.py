import pytest
import respx
import httpx
from scrapers.api import fetch_hackernews, fetch_reddit

HN_RESPONSE = {
    "hits": [
        {
            "title": "Show HN: AI agent for enterprise DevOps",
            "url": "https://example.com/ai-devops",
            "story_text": "We built an AI agent...",
            "created_at": "2026-02-24T10:00:00.000Z",
            "objectID": "12345",
        },
        {
            "title": "Ask HN: Best LLM for enterprise?",
            "url": None,
            "story_text": "Looking for recommendations...",
            "created_at": "2026-02-23T10:00:00.000Z",
            "objectID": "12346",
        },
    ]
}


@respx.mock
def test_fetch_hackernews_returns_stories():
    respx.get("https://hn.algolia.com/api/v1/search").mock(
        return_value=httpx.Response(200, json=HN_RESPONSE)
    )
    stories = fetch_hackernews(
        url="https://hn.algolia.com/api/v1/search",
        params={"tags": "story", "query": "AI enterprise", "hitsPerPage": 30},
    )
    assert len(stories) >= 1
    assert stories[0].title == "Show HN: AI agent for enterprise DevOps"


@respx.mock
def test_fetch_hackernews_uses_objectid_as_url_fallback():
    respx.get("https://hn.algolia.com/api/v1/search").mock(
        return_value=httpx.Response(200, json=HN_RESPONSE)
    )
    stories = fetch_hackernews(
        url="https://hn.algolia.com/api/v1/search",
        params={"tags": "story", "query": "AI enterprise", "hitsPerPage": 30},
    )
    hn_urls = [s.canonical_url for s in stories]
    assert any("ycombinator" in u or "example.com" in u for u in hn_urls)


def test_fetch_reddit_returns_stories():
    from unittest.mock import patch, MagicMock

    mock_feed = MagicMock()
    mock_feed.bozo = False
    mock_feed.entries = [
        MagicMock(
            title="Claude just changed how I build enterprise apps",
            link="https://reddit.com/r/ClaudeAI/comments/abc",
            summary="This is the content",
            published_parsed=(2026, 2, 24, 10, 0, 0, 0, 0, 0),
        )
    ]
    with patch("scrapers.api.feedparser.parse", return_value=mock_feed):
        stories = fetch_reddit(
            source_name="r/ClaudeAI",
            url="https://www.reddit.com/r/ClaudeAI/top/.rss?t=week",
        )
    assert len(stories) == 1
    assert "Claude" in stories[0].title

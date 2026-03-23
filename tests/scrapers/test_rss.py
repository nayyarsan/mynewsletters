from datetime import datetime, timezone, timedelta
from unittest.mock import patch, MagicMock
from scrapers.rss import fetch_rss

def _recent_tuple(days_ago: int) -> tuple:
    dt = datetime.now(tz=timezone.utc) - timedelta(days=days_ago)
    return (dt.year, dt.month, dt.day, dt.hour, dt.minute, dt.second, dt.weekday(), 0, 0)



MOCK_FEED = MagicMock()
MOCK_FEED.bozo = False
MOCK_FEED.entries = [
    MagicMock(
        title="GPT-5 is here",
        link="https://openai.com/gpt-5",
        summary="OpenAI launched GPT-5.",
        published_parsed=_recent_tuple(1),
    ),
    MagicMock(
        title="Claude 4 announced",
        link="https://anthropic.com/claude-4",
        summary="Anthropic announced Claude 4.",
        published_parsed=_recent_tuple(2),
    ),
]


def test_fetch_rss_returns_stories():
    with patch("scrapers.rss.feedparser.parse", return_value=MOCK_FEED):
        stories = fetch_rss(
            source_name="OpenAI",
            url="https://openai.com/news/rss.xml",
        )
    assert len(stories) == 2
    assert stories[0].title == "GPT-5 is here"
    assert stories[0].canonical_url == "https://openai.com/gpt-5"
    assert stories[0].sources[0].name == "OpenAI"


def test_fetch_rss_applies_filter_keywords():
    with patch("scrapers.rss.feedparser.parse", return_value=MOCK_FEED):
        stories = fetch_rss(
            source_name="OpenAI",
            url="https://openai.com/news/rss.xml",
            filter_keywords=["gpt"],
        )
    assert len(stories) == 1
    assert stories[0].title == "GPT-5 is here"


def test_fetch_rss_handles_bozo_feed():
    bad_feed = MagicMock()
    bad_feed.bozo = True
    bad_feed.entries = []
    with patch("scrapers.rss.feedparser.parse", return_value=bad_feed):
        stories = fetch_rss(source_name="Bad", url="https://bad.com/rss")
    assert stories == []


def test_fetch_rss_skips_entries_without_link():
    feed = MagicMock()
    feed.bozo = False
    entry = MagicMock(spec=["title", "summary", "published_parsed"])
    entry.title = "No link"
    entry.summary = "content"
    entry.published_parsed = _recent_tuple(1)
    feed.entries = [entry]
    with patch("scrapers.rss.feedparser.parse", return_value=feed):
        stories = fetch_rss(source_name="Test", url="https://test.com/rss")
    assert stories == []

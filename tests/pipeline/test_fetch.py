import pytest
import json
from pathlib import Path
from unittest.mock import patch, MagicMock
from schemas.story import Story
from datetime import datetime, timezone

MOCK_STORY = Story.from_url(
    url="https://openai.com/gpt-5",
    title="GPT-5 launches",
    source_name="OpenAI",
    published_at=datetime(2026, 2, 24, tzinfo=timezone.utc),
    raw_content="OpenAI launched GPT-5.",
)


def test_fetch_routes_rss_source():
    source = {
        "name": "openai",
        "display_name": "OpenAI",
        "type": "rss",
        "url": "https://openai.com/news/rss.xml",
        "weight": "high",
    }
    with patch("pipeline.fetch.fetch_rss", return_value=[MOCK_STORY]) as mock_rss:
        from pipeline.fetch import fetch_source
        stories = fetch_source(source)

    mock_rss.assert_called_once()
    assert len(stories) == 1


def test_fetch_routes_scrape_source():
    source = {
        "name": "cursor",
        "display_name": "Cursor",
        "type": "scrape",
        "url": "https://cursor.com/blog",
        "weight": "high",
    }
    with patch("pipeline.fetch.fetch_html", return_value=[MOCK_STORY]) as mock_html:
        from pipeline.fetch import fetch_source
        stories = fetch_source(source)

    mock_html.assert_called_once()
    assert len(stories) == 1


def test_fetch_saves_output_to_json(tmp_path):
    source = {
        "name": "openai",
        "display_name": "OpenAI",
        "type": "rss",
        "url": "https://openai.com/news/rss.xml",
        "weight": "high",
    }
    with patch("pipeline.fetch.fetch_rss", return_value=[MOCK_STORY]):
        from pipeline.fetch import fetch_source, save_stories
        stories = fetch_source(source)
        output_path = tmp_path / "openai.json"
        save_stories(stories, str(output_path))

    saved = json.loads(output_path.read_text())
    assert len(saved) == 1
    assert saved[0]["title"] == "GPT-5 launches"

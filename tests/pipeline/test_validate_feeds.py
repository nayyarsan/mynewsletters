import pytest
import json
import yaml
from unittest.mock import patch, MagicMock
from pipeline.validate_feeds import validate_sources, load_sources


def test_load_sources_reads_yaml(tmp_path):
    config = {"sources": [{"name": "test", "type": "rss", "url": "https://test.com/rss", "weight": "high"}]}
    config_file = tmp_path / "sources.yaml"
    config_file.write_text(yaml.dump(config))
    sources = load_sources(str(config_file))
    assert len(sources) == 1
    assert sources[0]["name"] == "test"


def test_validate_sources_marks_working_feed_as_active():
    mock_feed = MagicMock()
    mock_feed.bozo = False
    mock_feed.entries = [MagicMock(title="Test entry", link="https://test.com/1")]

    sources = [{"name": "test", "type": "rss", "url": "https://test.com/rss", "weight": "high"}]

    with patch("pipeline.validate_feeds.feedparser.parse", return_value=mock_feed):
        results = validate_sources(sources)

    assert results[0]["status"] == "active"
    assert results[0]["name"] == "test"


def test_validate_sources_marks_dead_feed_as_skipped():
    mock_feed = MagicMock()
    mock_feed.bozo = True
    mock_feed.entries = []

    sources = [{"name": "dead", "type": "rss", "url": "https://dead.com/rss", "weight": "high"}]

    with patch("pipeline.validate_feeds.feedparser.parse", return_value=mock_feed):
        results = validate_sources(sources)

    assert results[0]["status"] == "skipped"


def test_validate_sources_marks_scrape_sources_as_active():
    import respx
    import httpx

    sources = [{"name": "cursor", "type": "scrape", "url": "https://cursor.com/blog", "weight": "high"}]

    with respx.mock:
        respx.get("https://cursor.com/blog").mock(return_value=httpx.Response(200, text="<html></html>"))
        results = validate_sources(sources)

    assert results[0]["status"] == "active"

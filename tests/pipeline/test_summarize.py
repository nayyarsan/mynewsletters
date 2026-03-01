import pytest
import json
from pathlib import Path
from unittest.mock import MagicMock
from datetime import datetime, timedelta, timezone
from pipeline.summarize import summarize_story, pick_top3, load_cache, save_cache
from pipeline import summarize as mod
from schemas.story import Story, StorySummary

MOCK_STORY = Story.from_url(
    url="https://openai.com/gpt-5",
    title="GPT-5 launches with enterprise API",
    source_name="OpenAI",
    published_at=datetime(2026, 2, 24, tzinfo=timezone.utc),
    raw_content="OpenAI launched GPT-5 today with a new enterprise tier.",
)
MOCK_STORY.priority_category = "enterprise_software_delivery"
MOCK_STORY.priority_score = 90

MOCK_SUMMARY = json.dumps({
    "what_happened": "OpenAI launched GPT-5 with enterprise API access.",
    "enterprise_impact": "Enterprises can now integrate GPT-5 at scale.",
    "software_delivery_impact": "Dev teams can replace GPT-4 with GPT-5 in pipelines.",
    "developer_impact": "New API endpoints, higher context window, lower latency.",
    "human_impact": "More capable AI assistants across workplaces.",
    "how_to_use": "Upgrade your OpenAI SDK and switch model to gpt-5.",
})


def test_summarize_story_populates_summary():
    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = MagicMock(
        choices=[MagicMock(message=MagicMock(content=MOCK_SUMMARY))]
    )
    story = MOCK_STORY.model_copy(deep=True)
    result = summarize_story(story, mock_client)

    assert result.summary is not None
    assert "GPT-5" in result.summary.what_happened
    assert result.summary.how_to_use != ""


def test_summarize_story_handles_llm_failure():
    mock_client = MagicMock()
    mock_client.chat.completions.create.side_effect = Exception("API timeout")
    story = MOCK_STORY.model_copy(deep=True)
    result = summarize_story(story, mock_client)
    # Should return story unchanged (no summary), not raise
    assert result.summary is None


def test_pick_top3_selects_highest_scoring_across_categories():
    stories_by_category = {}
    for cat in ["enterprise_software_delivery", "enterprise_solutions", "finance_utilities"]:
        s = MOCK_STORY.model_copy(deep=True)
        s.priority_category = cat
        s.priority_score = 80
        stories_by_category[cat] = [s]

    top3 = pick_top3(stories_by_category)
    assert len(top3) == 3


def test_main_summarises_only_top3(monkeypatch, tmp_path):
    """Category stories must NOT be sent to the LLM — only top 3."""
    story_dict = {
        "id": "abc123",
        "title": "Category Story",
        "canonical_url": "https://example.com/cat",
        "sources": [{"name": "Test", "url": "https://example.com/cat"}],
        "published_at": "2026-02-28T00:00:00",
        "raw_content": "Some content.",
        "priority_category": "enterprise_software_delivery",
        "priority_score": 50,
        "summary": None,
    }
    ranked = {"enterprise_software_delivery": [story_dict]}
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (data_dir / "ranked.json").write_text(json.dumps(ranked))

    call_count = {"n": 0}

    def fake_summarize(story, client, cache=None):
        call_count["n"] += 1
        return story

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(mod, "summarize_story", fake_summarize)
    monkeypatch.setattr(mod, "get_client", lambda: None)

    mod.main()

    # top3 picks from 1 story → 1 call max. Category loop must NOT add more.
    assert call_count["n"] == 1


def test_pick_top3_prefers_fresh_over_stale():
    """A fresh story with equal score must beat a stale one for top 3."""
    fresh = MOCK_STORY.model_copy(deep=True)
    fresh.id = "fresh"
    fresh.priority_score = 80
    fresh.published_at = datetime.now(tz=timezone.utc) - timedelta(days=2)

    stale = MOCK_STORY.model_copy(deep=True)
    stale.id = "stale"
    stale.priority_score = 80
    stale.published_at = datetime.now(tz=timezone.utc) - timedelta(days=10)

    stories_by_category = {"enterprise_software_delivery": [fresh, stale]}
    top3 = pick_top3(stories_by_category)

    assert top3[0].id == "fresh"
    assert top3[1].id == "stale"


def test_load_cache_returns_empty_dict_when_file_missing(tmp_path):
    cache = load_cache(tmp_path / "no_such_file.json")
    assert cache == {}


def test_load_cache_evicts_entries_older_than_14_days(tmp_path):
    old_entry = {
        "summary": {"what_happened": "old", "enterprise_impact": "x",
                     "software_delivery_impact": "x", "developer_impact": "x",
                     "human_impact": "x", "how_to_use": "x"},
        "cached_at": (datetime.now(tz=timezone.utc) - timedelta(days=20)).isoformat(),
    }
    fresh_entry = {
        "summary": {"what_happened": "fresh", "enterprise_impact": "x",
                    "software_delivery_impact": "x", "developer_impact": "x",
                    "human_impact": "x", "how_to_use": "x"},
        "cached_at": (datetime.now(tz=timezone.utc) - timedelta(days=2)).isoformat(),
    }
    cache_file = tmp_path / "summary_cache.json"
    cache_file.write_text(json.dumps({
        "https://old.com": old_entry,
        "https://fresh.com": fresh_entry,
    }))

    cache = load_cache(cache_file)
    assert "https://old.com" not in cache
    assert "https://fresh.com" in cache


def test_save_cache_writes_json(tmp_path):
    cache = {"https://example.com": {"summary": {}, "cached_at": "2026-02-28T00:00:00+00:00"}}
    path = tmp_path / "data" / "summary_cache.json"
    save_cache(cache, path)
    assert path.exists()
    assert json.loads(path.read_text()) == cache


def test_summarize_story_uses_cache_hit():
    cache = {
        "https://openai.com/gpt-5": {
            "summary": {
                "what_happened": "Cached summary.",
                "enterprise_impact": "Cached impact.",
                "software_delivery_impact": "Cached delivery.",
                "developer_impact": "Cached dev.",
                "human_impact": "Cached human.",
                "how_to_use": "Cached use.",
            },
            "cached_at": datetime.now(tz=timezone.utc).isoformat(),
        }
    }
    mock_client = MagicMock()
    story = MOCK_STORY.model_copy(deep=True)

    result = summarize_story(story, mock_client, cache=cache)

    # LLM must NOT be called
    mock_client.chat.completions.create.assert_not_called()
    assert result.summary is not None
    assert result.summary.what_happened == "Cached summary."


def test_summarize_story_populates_cache_on_miss():
    cache = {}
    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = MagicMock(
        choices=[MagicMock(message=MagicMock(content=MOCK_SUMMARY))]
    )
    story = MOCK_STORY.model_copy(deep=True)

    summarize_story(story, mock_client, cache=cache)

    assert "https://openai.com/gpt-5" in cache
    assert "cached_at" in cache["https://openai.com/gpt-5"]
    assert cache["https://openai.com/gpt-5"]["summary"]["what_happened"] != ""

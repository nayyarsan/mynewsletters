import pytest
import json
from pathlib import Path
from unittest.mock import MagicMock
from datetime import datetime, timezone
from pipeline.summarize import summarize_story, pick_top3
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

    def fake_summarize(story, client):
        call_count["n"] += 1
        return story

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(mod, "summarize_story", fake_summarize)
    monkeypatch.setattr(mod, "get_client", lambda: None)

    mod.main()

    # top3 picks from 1 story → 1 call max. Category loop must NOT add more.
    assert call_count["n"] == 1

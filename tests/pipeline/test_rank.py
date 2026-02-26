import pytest
import json
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone
from pipeline.rank import rank_story, select_top_stories
from schemas.story import Story

MOCK_STORY = Story.from_url(
    url="https://openai.com/gpt-5",
    title="GPT-5 launches with enterprise API",
    source_name="OpenAI",
    published_at=datetime(2026, 2, 24, tzinfo=timezone.utc),
    raw_content="OpenAI launched GPT-5 with a new enterprise API tier.",
)

MOCK_LLM_RESPONSE = json.dumps({
    "scores": {
        "enterprise_software_delivery": 85,
        "enterprise_solutions": 70,
        "finance_utilities": 30,
        "general_significance": 90,
    },
    "include": True,
})


def test_rank_story_sets_category_and_score():
    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = MagicMock(
        choices=[MagicMock(message=MagicMock(content=MOCK_LLM_RESPONSE))]
    )
    story = MOCK_STORY.model_copy(deep=True)
    ranked = rank_story(story, mock_client)

    assert ranked.priority_category == "general_significance"
    assert ranked.priority_score == 90


def test_rank_story_exclude_returns_none():
    exclude_response = json.dumps({
        "scores": {
            "enterprise_software_delivery": 5,
            "enterprise_solutions": 5,
            "finance_utilities": 5,
            "general_significance": 5,
        },
        "include": False,
    })
    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = MagicMock(
        choices=[MagicMock(message=MagicMock(content=exclude_response))]
    )
    story = MOCK_STORY.model_copy(deep=True)
    result = rank_story(story, mock_client)
    assert result is None


def test_select_top_stories_caps_per_category():
    stories = []
    for i in range(10):
        s = MOCK_STORY.model_copy(deep=True)
        s.id = str(i)
        s.priority_category = "enterprise_software_delivery"
        s.priority_score = 90 - i
        stories.append(s)

    result = select_top_stories(stories, per_category=5)
    assert len(result["enterprise_software_delivery"]) <= 5

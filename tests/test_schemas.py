import pytest
from schemas.story import Story, StorySource, StorySummary
from datetime import datetime, timezone


def test_story_creation_minimal():
    story = Story(
        id="abc123",
        title="GPT-5 launches",
        canonical_url="https://openai.com/gpt-5",
        sources=[StorySource(name="OpenAI", url="https://openai.com/gpt-5")],
        published_at=datetime(2026, 2, 24, tzinfo=timezone.utc),
        raw_content="OpenAI launched GPT-5 today.",
    )
    assert story.id == "abc123"
    assert story.source_count == 1
    assert story.priority_category is None
    assert story.priority_score is None
    assert story.summary is None


def test_story_id_generated_from_url():
    story = Story.from_url(
        url="https://openai.com/gpt-5",
        title="GPT-5 launches",
        source_name="OpenAI",
        published_at=datetime(2026, 2, 24, tzinfo=timezone.utc),
        raw_content="OpenAI launched GPT-5 today.",
    )
    assert len(story.id) == 64  # sha256 hex digest


def test_story_source_count_reflects_sources():
    story = Story.from_url(
        url="https://openai.com/gpt-5",
        title="GPT-5 launches",
        source_name="OpenAI",
        published_at=datetime(2026, 2, 24, tzinfo=timezone.utc),
        raw_content="Content",
    )
    story.sources.append(StorySource(name="Hacker News", url="https://news.ycombinator.com/1"))
    assert story.source_count == 2


def test_story_serializes_to_dict():
    story = Story.from_url(
        url="https://openai.com/gpt-5",
        title="GPT-5 launches",
        source_name="OpenAI",
        published_at=datetime(2026, 2, 24, tzinfo=timezone.utc),
        raw_content="Content",
    )
    d = story.model_dump(mode="json")
    assert d["title"] == "GPT-5 launches"
    assert isinstance(d["sources"], list)

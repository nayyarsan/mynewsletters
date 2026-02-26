import pytest
import json
from datetime import datetime, timezone
from pipeline.normalize import (
    load_raw_stories,
    deduplicate_by_url,
    deduplicate_by_title_similarity,
    normalize,
)
from schemas.story import Story, StorySource


def make_story(url, title, source="OpenAI", content="content"):
    return Story.from_url(
        url=url,
        title=title,
        source_name=source,
        published_at=datetime(2026, 2, 24, tzinfo=timezone.utc),
        raw_content=content,
    )


def test_deduplicate_by_url_merges_same_url():
    s1 = make_story("https://openai.com/gpt-5", "GPT-5 launches", "OpenAI")
    s2 = make_story("https://openai.com/gpt-5", "GPT-5 launches", "TLDR AI")

    result = deduplicate_by_url([s1, s2])
    assert len(result) == 1
    assert result[0].source_count == 2
    assert {s.name for s in result[0].sources} == {"OpenAI", "TLDR AI"}


def test_deduplicate_by_url_keeps_different_urls():
    s1 = make_story("https://openai.com/gpt-5", "GPT-5 launches", "OpenAI")
    s2 = make_story("https://hn.com/item?id=1", "GPT-5 launches", "HN")

    result = deduplicate_by_url([s1, s2])
    assert len(result) == 2


def test_deduplicate_by_title_similarity_merges_similar_titles():
    s1 = make_story("https://openai.com/gpt-5", "OpenAI launches GPT-5 model", "OpenAI")
    s2 = make_story("https://hn.com/1", "OpenAI launches GPT-5 model today", "HN")

    result = deduplicate_by_title_similarity([s1, s2], threshold=0.6)
    assert len(result) == 1
    assert result[0].source_count == 2


def test_deduplicate_by_title_similarity_keeps_different_stories():
    s1 = make_story("https://openai.com/gpt-5", "GPT-5 model released", "OpenAI")
    s2 = make_story("https://anthropic.com/claude-4", "Claude 4 announced", "Anthropic")

    result = deduplicate_by_title_similarity([s1, s2], threshold=0.6)
    assert len(result) == 2


def test_source_count_boosts_are_preserved():
    s1 = make_story("https://openai.com/gpt-5", "GPT-5 launches", "OpenAI")
    s2 = make_story("https://openai.com/gpt-5", "GPT-5 launches", "TLDR AI")
    s3 = make_story("https://openai.com/gpt-5", "GPT-5 launches", "HN")

    result = deduplicate_by_url([s1, s2, s3])
    assert result[0].source_count == 3

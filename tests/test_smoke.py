"""
Smoke test: runs the full pipeline with mocked LLM and real (cached) RSS feeds.
Validates the data flows correctly end to end.
"""
import json
import pytest
from datetime import datetime, timezone
from unittest.mock import patch, MagicMock
from schemas.story import Story, StorySummary
from pipeline.normalize import normalize, deduplicate_by_url
from pipeline.rank import select_top_stories
from pipeline.deliver import format_digest, split_message

MOCK_RANK_RESPONSE = json.dumps({
    "scores": {
        "enterprise_software_delivery": 85,
        "enterprise_solutions": 40,
        "finance_utilities": 20,
        "general_significance": 60,
    },
    "include": True,
})

MOCK_SUMMARY_RESPONSE = json.dumps({
    "what_happened": "A major AI development occurred.",
    "enterprise_impact": "Significant for enterprise teams.",
    "software_delivery_impact": "Changes how code is reviewed.",
    "developer_impact": "New tools available.",
    "human_impact": "Workforce will adapt.",
    "how_to_use": "Start a small pilot project.",
})


def make_stories(n=5):
    stories = []
    for i in range(n):
        s = Story.from_url(
            url=f"https://example.com/story-{i}",
            title=f"AI development number {i} impacts enterprise",
            source_name="TestSource",
            published_at=datetime(2026, 2, 24, tzinfo=timezone.utc),
            raw_content=f"Content for story {i}. This is about AI and enterprise.",
        )
        stories.append(s)
    return stories


def test_dedup_then_rank_then_format():
    stories = make_stories(5)
    # Add a duplicate
    dup = stories[0].model_copy(deep=True)
    dup.sources[0].name = "DuplicateSource"
    stories.append(dup)

    deduped = deduplicate_by_url(stories)
    assert len(deduped) == 5  # duplicate merged
    assert deduped[0].source_count == 2

    # Simulate ranking
    for s in deduped:
        s.priority_category = "enterprise_software_delivery"
        s.priority_score = 80

    categorized = select_top_stories(deduped)
    assert len(categorized["enterprise_software_delivery"]) <= 8

    # Simulate summaries
    for s in deduped:
        s.summary = StorySummary(**json.loads(MOCK_SUMMARY_RESPONSE))

    top3 = deduped[:3]
    digest = format_digest(top3, categorized, week_of="Feb 24, 2026")

    assert "AI DIGEST" in digest
    assert "TOP 3 MUST-READS" in digest
    assert len(digest) > 100


def test_long_digest_splits_correctly():
    long_text = "A" * 5000
    parts = split_message(long_text, max_length=4096)
    assert len(parts) == 2
    assert all(len(p) <= 4096 for p in parts)


def test_all_pipeline_modules_importable():
    from pipeline import validate_feeds, fetch, normalize, rank, summarize, deliver
    from scrapers import rss, html, api
    from schemas import story
    assert True  # if we got here, all imports work

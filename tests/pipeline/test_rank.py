import pytest
import json
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone, timedelta
from pipeline.rank import rank_story, rank_batch, select_top_stories, heuristic_prescore, presort_and_limit, recency_multiplier, PRESCORE_LIMIT
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

MOCK_BATCH_RESPONSE = json.dumps({
    "stories": [
        {
            "index": 0,
            "scores": {
                "enterprise_software_delivery": 85,
                "enterprise_solutions": 70,
                "finance_utilities": 30,
                "general_significance": 90,
            },
            "include": True,
        },
        {
            "index": 1,
            "scores": {
                "enterprise_software_delivery": 10,
                "enterprise_solutions": 5,
                "finance_utilities": 5,
                "general_significance": 10,
            },
            "include": False,
        },
    ]
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


def test_rank_batch_returns_only_included():
    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = MagicMock(
        choices=[MagicMock(message=MagicMock(content=MOCK_BATCH_RESPONSE))]
    )
    story_a = MOCK_STORY.model_copy(deep=True)
    story_b = MOCK_STORY.model_copy(deep=True)
    story_b.id = "other"
    results = rank_batch([story_a, story_b], mock_client)

    # Only index 0 has include=True and high scores
    assert len(results) == 1
    assert results[0].priority_category == "general_significance"
    assert results[0].priority_score == 90


def test_rank_batch_handles_llm_failure():
    mock_client = MagicMock()
    mock_client.chat.completions.create.side_effect = Exception("timeout")
    results = rank_batch([MOCK_STORY.model_copy(deep=True)], mock_client)
    assert results == []


def test_heuristic_prescore_multi_source_bonus():
    from schemas.story import StorySource
    story = MOCK_STORY.model_copy(deep=True)
    story.sources.append(StorySource(name="HN", url="https://hn.com/x"))
    score_multi = heuristic_prescore(story, {})
    score_single = heuristic_prescore(MOCK_STORY, {})
    assert score_multi > score_single


def test_heuristic_prescore_keyword_bonus():
    story_with_kw = Story.from_url(
        url="https://example.com/1",
        title="Enterprise agent deployment platform",
        source_name="test",
        published_at=datetime(2026, 2, 24, tzinfo=timezone.utc),
        raw_content="test",
    )
    story_no_kw = Story.from_url(
        url="https://example.com/2",
        title="Random news about weather",
        source_name="test",
        published_at=datetime(2026, 2, 24, tzinfo=timezone.utc),
        raw_content="test",
    )
    assert heuristic_prescore(story_with_kw, {}) > heuristic_prescore(story_no_kw, {})


def test_presort_and_limit_keeps_top_n():
    stories = []
    for i in range(10):
        s = Story.from_url(
            url=f"https://example.com/{i}",
            title=f"Story {i}",
            source_name="test",
            published_at=datetime(2026, 2, 24, tzinfo=timezone.utc),
            raw_content="test",
        )
        stories.append(s)
    result = presort_and_limit(stories, {}, limit=5)
    assert len(result) == 5


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


def test_recency_multiplier_fresh_story():
    pub = datetime.now(tz=timezone.utc) - timedelta(days=3)
    assert recency_multiplier(pub) == 1.0


def test_recency_multiplier_week_old():
    pub = datetime.now(tz=timezone.utc) - timedelta(days=7)
    assert recency_multiplier(pub) == 1.0


def test_recency_multiplier_ten_days_old():
    pub = datetime.now(tz=timezone.utc) - timedelta(days=10)
    assert recency_multiplier(pub) == 0.5


def test_recency_multiplier_naive_datetime():
    """Naive datetimes (no tzinfo) must be handled without raising."""
    pub = datetime.now() - timedelta(days=3)
    assert recency_multiplier(pub) == 1.0


def test_heuristic_prescore_decays_old_story():
    fresh = Story.from_url(
        url="https://example.com/fresh",
        title="Enterprise agent platform",
        source_name="test",
        published_at=datetime.now(tz=timezone.utc) - timedelta(days=2),
        raw_content="test",
    )
    old = Story.from_url(
        url="https://example.com/old",
        title="Enterprise agent platform",
        source_name="test",
        published_at=datetime.now(tz=timezone.utc) - timedelta(days=10),
        raw_content="test",
    )
    assert heuristic_prescore(fresh, {}) > heuristic_prescore(old, {})


def test_14_day_cutoff_in_main(monkeypatch, tmp_path):
    """Stories older than 14 days must be dropped before ranking."""
    import json
    from pathlib import Path
    from pipeline import rank as mod

    fresh_story = {
        "id": "fresh1",
        "title": "Fresh Story",
        "canonical_url": "https://example.com/fresh",
        "sources": [{"name": "Test", "url": "https://example.com/fresh"}],
        "published_at": (datetime.now(tz=timezone.utc) - timedelta(days=2)).isoformat(),
        "raw_content": "Some content.",
        "priority_category": None,
        "priority_score": None,
        "summary": None,
    }
    old_story = {
        "id": "old1",
        "title": "Old Story",
        "canonical_url": "https://example.com/old",
        "sources": [{"name": "Test", "url": "https://example.com/old"}],
        "published_at": (datetime.now(tz=timezone.utc) - timedelta(days=20)).isoformat(),
        "raw_content": "Some content.",
        "priority_category": None,
        "priority_score": None,
        "summary": None,
    }
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (data_dir / "normalized.json").write_text(json.dumps([fresh_story, old_story]))
    (tmp_path / "sources").mkdir()
    (tmp_path / "sources" / "sources.yaml").write_text("sources: []")

    seen_stories = []

    def fake_presort(stories, weights, limit=40):
        seen_stories.extend(stories)
        return []

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(mod, "presort_and_limit", fake_presort)
    monkeypatch.setattr(mod, "get_client", lambda: None)
    monkeypatch.setattr(mod, "_load_source_weights", lambda: {})

    mod.main()

    urls = [s.canonical_url for s in seen_stories]
    assert "https://example.com/fresh" in urls
    assert "https://example.com/old" not in urls


def test_select_top_stories_prefers_fresh_over_stale():
    fresh = MOCK_STORY.model_copy(deep=True)
    fresh.id = "fresh"
    fresh.priority_category = "enterprise_software_delivery"
    fresh.priority_score = 80
    fresh.published_at = datetime.now(tz=timezone.utc) - timedelta(days=2)

    stale = MOCK_STORY.model_copy(deep=True)
    stale.id = "stale"
    stale.priority_category = "enterprise_software_delivery"
    stale.priority_score = 80   # same score — recency should break the tie
    stale.published_at = datetime.now(tz=timezone.utc) - timedelta(days=10)

    result = select_top_stories([fresh, stale], per_category=2)
    ordered = result["enterprise_software_delivery"]
    assert ordered[0].id == "fresh"
    assert ordered[1].id == "stale"

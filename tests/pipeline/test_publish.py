import json
import pytest
from datetime import datetime, timezone
from pathlib import Path
from schemas.story import Story
from pipeline.publish import build_rdradar, _action_for_tags, _reason_for_story, main


def _make_story(url: str, sdlc_tags: list[str]) -> Story:
    s = Story.from_url(
        url=url,
        title=f"Story about {url}",
        source_name="TestSource",
        published_at=datetime(2026, 3, 1, tzinfo=timezone.utc),
        raw_content="Some content about AI and software delivery.",
    )
    s.sdlc_tags = sdlc_tags
    return s


# ── _action_for_tags ─────────────────────────────────────────────────────────

def test_action_for_tags_ai_agents():
    assert _action_for_tags(["ai-agents"]) == "spike"


def test_action_for_tags_delivery():
    assert _action_for_tags(["delivery"]) == "spike"


def test_action_for_tags_governance():
    assert _action_for_tags(["governance"]) == "review"


def test_action_for_tags_tooling():
    assert _action_for_tags(["tooling"]) == "evaluate"


def test_action_for_tags_priority_order():
    # ai-agents wins over governance
    assert _action_for_tags(["governance", "ai-agents"]) == "spike"


# ── build_rdradar ─────────────────────────────────────────────────────────────

def test_build_rdradar_excludes_general_only():
    story = _make_story("https://example.com/1", ["general"])
    payload = build_rdradar([story], [])
    assert payload["items"] == []


def test_build_rdradar_includes_high_signal_personal():
    story = _make_story("https://example.com/2", ["tooling"])
    payload = build_rdradar([story], [])
    assert len(payload["items"]) == 1
    assert payload["items"][0]["source"] == "personal"
    assert payload["items"][0]["sdlc_tags"] == ["tooling"]


def test_build_rdradar_includes_high_signal_enterprise():
    story = _make_story("https://example.com/3", ["ai-agents"])
    payload = build_rdradar([], [story])
    assert len(payload["items"]) == 1
    assert payload["items"][0]["source"] == "enterprise"


def test_build_rdradar_deduplicates_by_url():
    story = _make_story("https://example.com/4", ["delivery"])
    payload = build_rdradar([story], [story])
    # Same URL should appear only once (enterprise takes precedence)
    assert len(payload["items"]) == 1
    assert payload["items"][0]["source"] == "enterprise"


def test_build_rdradar_enterprise_items_listed_first():
    p_story = _make_story("https://example.com/personal", ["tooling"])
    e_story = _make_story("https://example.com/enterprise", ["governance"])
    payload = build_rdradar([p_story], [e_story])
    assert len(payload["items"]) == 2
    assert payload["items"][0]["source"] == "enterprise"
    assert payload["items"][1]["source"] == "personal"


def test_build_rdradar_has_generated_at():
    payload = build_rdradar([], [])
    assert "generated_at" in payload
    # Should be parseable as ISO datetime
    datetime.fromisoformat(payload["generated_at"])


def test_build_rdradar_recommendation_fields():
    story = _make_story("https://example.com/5", ["delivery"])
    payload = build_rdradar([story], [])
    rec = payload["items"][0]["recommendation"]
    assert "action" in rec
    assert "reason" in rec
    assert rec["action"] == "spike"


def test_build_rdradar_strips_general_from_sdlc_tags():
    story = _make_story("https://example.com/6", ["tooling", "general"])
    payload = build_rdradar([story], [])
    assert "general" not in payload["items"][0]["sdlc_tags"]
    assert "tooling" in payload["items"][0]["sdlc_tags"]


# ── main() integration test ───────────────────────────────────────────────────

def test_main_writes_rdradar_json(monkeypatch, tmp_path):
    story_dict = {
        "id": "abc1",
        "title": "AI governance update",
        "canonical_url": "https://example.com/gov",
        "sources": [{"name": "Test", "url": "https://example.com/gov"}],
        "published_at": "2026-03-01T00:00:00+00:00",
        "raw_content": "AI governance tooling release.",
        "priority_category": "enterprise_solutions",
        "priority_score": 80,
        "summary": None,
        "sdlc_tags": ["governance"],
    }
    ranked = {
        "personal_items": [story_dict],
        "enterprise_items": [story_dict],
    }
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (data_dir / "ranked.json").write_text(json.dumps(ranked))
    monkeypatch.chdir(tmp_path)

    main()

    rdradar = json.loads((data_dir / "rdradar.json").read_text())
    assert "generated_at" in rdradar
    assert len(rdradar["items"]) == 1  # deduplicated
    assert rdradar["items"][0]["source"] == "enterprise"
    assert rdradar["items"][0]["sdlc_tags"] == ["governance"]

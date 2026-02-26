import pytest
from datetime import datetime, timezone
from pipeline.deliver import format_story_full, format_story_brief, format_digest
from schemas.story import Story, StorySource, StorySummary


def make_full_story(title, category, score, source_names=None):
    s = Story.from_url(
        url=f"https://example.com/{title.replace(' ', '-')}",
        title=title,
        source_name=source_names[0] if source_names else "OpenAI",
        published_at=datetime(2026, 2, 24, tzinfo=timezone.utc),
        raw_content="Content here.",
    )
    s.priority_category = category
    s.priority_score = score
    if source_names and len(source_names) > 1:
        for name in source_names[1:]:
            s.sources.append(StorySource(name=name, url=f"https://{name}.com"))
    s.summary = StorySummary(
        what_happened="OpenAI launched GPT-5.",
        enterprise_impact="Major productivity gains for enterprises.",
        software_delivery_impact="Dev teams can automate code review.",
        developer_impact="New API available, upgrade SDK.",
        human_impact="Jobs will shift, not disappear.",
        how_to_use="Try the new API with a small project this week.",
    )
    return s


def test_format_story_full_contains_all_sections():
    story = make_full_story("GPT-5 launches", "enterprise_software_delivery", 90)
    text = format_story_full(story, index=1)

    assert "[1]" in text
    assert "GPT-5 launches" in text
    assert "What happened:" in text
    assert "Enterprise impact:" in text
    assert "Software delivery impact:" in text
    assert "For developers:" in text
    assert "For people:" in text
    assert "How to use it:" in text
    assert "https://example.com" in text


def test_format_story_full_shows_multiple_sources():
    story = make_full_story("GPT-5 launches", "enterprise_software_delivery", 90,
                            source_names=["OpenAI", "Hacker News", "TLDR AI"])
    text = format_story_full(story, index=1)
    assert "3 sources" in text or "OpenAI" in text


def test_format_story_brief_is_one_line():
    story = make_full_story("GPT-5 launches", "enterprise_software_delivery", 90)
    text = format_story_brief(story)
    assert "GPT-5 launches" in text
    assert "https://example.com" in text
    assert "\n\n" not in text


def test_format_digest_has_all_categories():
    stories_by_category = {
        "enterprise_software_delivery": [
            make_full_story("Story A", "enterprise_software_delivery", 90)
        ],
        "enterprise_solutions": [
            make_full_story("Story B", "enterprise_solutions", 75)
        ],
        "finance_utilities": [],
        "general_significance": [
            make_full_story("Story C", "general_significance", 60)
        ],
    }
    top3 = [make_full_story("Top Story", "enterprise_software_delivery", 95)]
    digest = format_digest(top3, stories_by_category, week_of="Feb 24, 2026")

    assert "AI DIGEST" in digest
    assert "TOP 3 MUST-READS" in digest
    assert "ENTERPRISE SOFTWARE DELIVERY" in digest
    assert "ENTERPRISE SOLUTIONS" in digest
    assert "GENERAL SIGNIFICANCE" in digest
    assert "FINANCE & UTILITIES" in digest

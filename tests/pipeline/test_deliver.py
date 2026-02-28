import pytest
from datetime import datetime, timezone
from pipeline.deliver import format_story_full, format_story_brief, format_digest
from schemas.story import Story, StorySource, StorySummary


def make_story(title, category, score, url=None, source_names=None, with_summary=True):
    url = url or f"https://example.com/{title.replace(' ', '-')}"
    s = Story.from_url(
        url=url,
        title=title,
        source_name=source_names[0] if source_names else "OpenAI",
        published_at=datetime(2026, 2, 28, tzinfo=timezone.utc),
        raw_content="Content here.",
    )
    s.priority_category = category
    s.priority_score = score
    if source_names and len(source_names) > 1:
        for name in source_names[1:]:
            s.sources.append(StorySource(name=name, url=f"https://{name}.com"))
    if with_summary:
        s.summary = StorySummary(
            what_happened="OpenAI launched GPT-5.",
            enterprise_impact="Major productivity gains for enterprises.",
            software_delivery_impact="Dev teams can automate code review.",
            developer_impact="New API available, upgrade SDK.",
            human_impact="Jobs will shift, not disappear.",
            how_to_use="Try the new API with a small project this week.",
        )
    return s


# --- format_story_full ---

def test_format_story_full_uses_html_bold_for_title():
    story = make_story("GPT-5 launches", "enterprise_software_delivery", 90)
    text = format_story_full(story, index=1)
    assert "<b>" in text and "</b>" in text
    assert "GPT-5 launches" in text


def test_format_story_full_contains_all_summary_sections():
    story = make_story("GPT-5 launches", "enterprise_software_delivery", 90)
    text = format_story_full(story, index=1)
    assert "What happened:" in text
    assert "Enterprise impact:" in text
    assert "For developers:" in text
    assert "How to use it:" in text


def test_format_story_full_contains_read_more_link():
    story = make_story("GPT-5 launches", "enterprise_software_delivery", 90)
    text = format_story_full(story, index=1)
    assert "https://example.com" in text
    assert "🔗" in text


def test_format_story_full_no_summary_still_renders():
    story = make_story("GPT-5 launches", "enterprise_software_delivery", 90, with_summary=False)
    text = format_story_full(story, index=1)
    assert "GPT-5 launches" in text
    assert "What happened:" not in text


# --- format_story_brief ---

def test_format_story_brief_uses_html_anchor():
    story = make_story("GPT-5 launches", "enterprise_software_delivery", 90)
    text = format_story_brief(story)
    assert '<a href=' in text
    assert "GPT-5 launches" in text


def test_format_story_brief_has_no_double_blank_lines():
    story = make_story("GPT-5 launches", "enterprise_software_delivery", 90)
    text = format_story_brief(story)
    assert "\n\n" not in text


# --- format_digest ---

def test_format_digest_excludes_top3_from_category_sections():
    top_story = make_story("Top Story", "enterprise_software_delivery", 95,
                           url="https://example.com/top")
    cat_story = make_story("Cat Story", "enterprise_software_delivery", 70,
                           url="https://example.com/cat")
    stories_by_category = {
        "enterprise_software_delivery": [top_story, cat_story],
        "enterprise_solutions": [],
        "finance_utilities": [],
        "general_significance": [],
    }
    digest = format_digest([top_story], stories_by_category, week_of="Feb 28, 2026")
    # Top Story appears once in TOP 3, NOT again in category section
    assert digest.count("Top Story") == 1
    # Cat Story appears in category section
    assert "Cat Story" in digest


def test_format_digest_hides_empty_categories():
    top_story = make_story("Top Story", "enterprise_software_delivery", 95)
    stories_by_category = {
        "enterprise_software_delivery": [top_story],
        "enterprise_solutions": [],
        "finance_utilities": [],
        "general_significance": [],
    }
    digest = format_digest([top_story], stories_by_category, week_of="Feb 28, 2026")
    assert "ENTERPRISE SOLUTIONS" not in digest
    assert "FINANCE & UTILITIES" not in digest
    assert "No significant stories" not in digest


def test_format_digest_shows_non_empty_categories():
    story_a = make_story("Story A", "enterprise_software_delivery", 90)
    story_b = make_story("Story B", "general_significance", 60)
    stories_by_category = {
        "enterprise_software_delivery": [story_a],
        "enterprise_solutions": [],
        "finance_utilities": [],
        "general_significance": [story_b],
    }
    digest = format_digest([story_a], stories_by_category, week_of="Feb 28, 2026")
    assert "ENTERPRISE SOFTWARE DELIVERY" in digest
    assert "GENERAL SIGNIFICANCE" in digest
    assert "Story B" in digest

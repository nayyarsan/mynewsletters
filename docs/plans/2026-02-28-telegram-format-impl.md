# Telegram Output Improvements — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Fix missing LLM summaries in the digest and improve Telegram formatting with HTML, deduplication, and empty-category suppression.

**Architecture:** Two files change — `pipeline/summarize.py` (remove over-eager category summarise loop) and `pipeline/deliver.py` (HTML formatting, dedup, hide empty cats). Tests for both files are updated to match new behaviour.

**Tech Stack:** Python 3.12, python-telegram-bot, pytest, pydantic

---

### Task 1: Fix summarize.py — summarise top 3 only

**Files:**
- Modify: `pipeline/summarize.py:88-92`
- Test: `tests/pipeline/test_summarize.py`

**Step 1: Run existing tests to establish a green baseline**

```bash
pytest tests/pipeline/test_summarize.py -v
```

Expected: All 3 tests PASS.

**Step 2: Add a failing test that verifies category stories are NOT summarised**

Add to `tests/pipeline/test_summarize.py`:

```python
def test_main_summarises_only_top3(monkeypatch, tmp_path):
    """Category stories must NOT be sent to the LLM — only top 3."""
    import json
    from pathlib import Path
    from pipeline import summarize as mod

    # Build minimal ranked.json with one category story
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
    assert call_count["n"] <= 1
```

**Step 3: Run to verify it fails**

```bash
pytest tests/pipeline/test_summarize.py::test_main_summarises_only_top3 -v
```

Expected: FAIL (current code makes more than 1 call — the category loop runs too).

**Step 4: Remove the category summarise loop in summarize.py**

In `pipeline/summarize.py`, delete lines 90–92:

```python
# DELETE these three lines:
    print(f"Summarizing category stories...")
    for cat, stories in stories_by_category.items():
        stories_by_category[cat] = [summarize_story(s, client) for s in stories]
```

After deletion, `main()` ends with:

```python
    top3 = pick_top3(stories_by_category)
    print(f"Summarizing top 3 must-reads...")
    top3 = [summarize_story(s, client) for s in top3]

    output = {
        "top3": [s.model_dump(mode="json") for s in top3],
        "categories": {
            cat: [s.model_dump(mode="json") for s in stories]
            for cat, stories in stories_by_category.items()
        },
    }
    Path("data/summarized.json").write_text(json.dumps(output, indent=2, default=str))
    print("  Saved to data/summarized.json")
```

**Step 5: Run all summarize tests**

```bash
pytest tests/pipeline/test_summarize.py -v
```

Expected: All 4 tests PASS.

**Step 6: Commit**

```bash
git add pipeline/summarize.py tests/pipeline/test_summarize.py
git commit -m "fix: summarise only top 3 stories to stay within rate limits"
```

---

### Task 2: Update deliver.py — HTML format, dedup, hide empty categories

**Files:**
- Modify: `pipeline/deliver.py`
- Test: `tests/pipeline/test_deliver.py`

**Step 1: Run existing deliver tests to establish baseline**

```bash
pytest tests/pipeline/test_deliver.py -v
```

Expected: All 4 tests PASS.

**Step 2: Write failing tests for the new behaviour**

Replace the entire content of `tests/pipeline/test_deliver.py` with:

```python
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
```

**Step 3: Run to verify tests fail**

```bash
pytest tests/pipeline/test_deliver.py -v
```

Expected: Multiple failures — HTML tags not present, dedup not implemented, empty cats still shown.

**Step 4: Rewrite deliver.py**

Replace the entire content of `pipeline/deliver.py` with:

```python
"""
Job 5: Format stories and deliver to Telegram.

Format: Top 3 must-reads in full (HTML), then category digests.
Uses Telegram HTML parse mode. No emoji except 🔗 on links.
"""
import json
import os
import asyncio
from datetime import datetime, timezone
from pathlib import Path
from telegram import Bot
from schemas.story import Story

CATEGORY_LABELS = {
    "enterprise_software_delivery": "ENTERPRISE SOFTWARE DELIVERY",
    "enterprise_solutions": "ENTERPRISE SOLUTIONS",
    "finance_utilities": "FINANCE & UTILITIES",
    "general_significance": "GENERAL SIGNIFICANCE",
}

MAX_TELEGRAM_LENGTH = 4096
DIVIDER = "─" * 32


def _escape(text: str) -> str:
    """Escape HTML special chars for Telegram HTML mode."""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def format_story_full(story: Story, index: int) -> str:
    sources_str = " | ".join(s.name for s in story.sources)
    if story.source_count > 1:
        sources_str += f" ({story.source_count} sources)"
    category_label = CATEGORY_LABELS.get(story.priority_category, story.priority_category or "")

    lines = [
        f"<b>{index}. {_escape(story.title)}</b>",
        f"<i>{_escape(sources_str)} · {_escape(category_label)}</i>",
        "",
    ]

    if story.summary:
        lines += [
            f"What happened: {_escape(story.summary.what_happened)}",
            f"Enterprise impact: {_escape(story.summary.enterprise_impact)}",
            f"For developers: {_escape(story.summary.developer_impact)}",
            f"How to use it: {_escape(story.summary.how_to_use)}",
            "",
        ]

    for src in story.sources:
        lines.append(f"🔗 Read more: {src.url}")

    return "\n".join(lines)


def format_story_brief(story: Story) -> str:
    return f'• <a href="{story.canonical_url}">{_escape(story.title)}</a>'


def format_digest(
    top3: list[Story],
    stories_by_category: dict[str, list[Story]],
    week_of: str,
) -> str:
    top3_urls = {s.canonical_url for s in top3}

    sections = [
        f"<b>AI DIGEST</b> | Week of {week_of}",
        "",
        f"<b>TOP 3 MUST-READS THIS WEEK</b>",
        "",
    ]

    for i, story in enumerate(top3, 1):
        sections.append(format_story_full(story, index=i))
        sections.append("")

    for cat, label in CATEGORY_LABELS.items():
        stories = [s for s in stories_by_category.get(cat, []) if s.canonical_url not in top3_urls]
        if not stories:
            continue
        sections += [DIVIDER, f"<b>{label}</b>", ""]
        for story in stories:
            sections.append(format_story_brief(story))
        sections.append("")

    return "\n".join(sections)


def split_message(text: str, max_length: int = MAX_TELEGRAM_LENGTH) -> list[str]:
    if len(text) <= max_length:
        return [text]

    parts = []
    while text:
        if len(text) <= max_length:
            parts.append(text)
            break
        split_at = text[:max_length].rfind("\n")
        if split_at == -1:
            split_at = max_length
        parts.append(text[:split_at])
        text = text[split_at:].lstrip("\n")
    return parts


async def send_to_telegram(text: str, bot_token: str, chat_id: str) -> None:
    bot = Bot(token=bot_token)
    parts = split_message(text)
    for part in parts:
        await bot.send_message(
            chat_id=chat_id,
            text=part,
            parse_mode="HTML",
            disable_web_page_preview=True,
        )


def main():
    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if not bot_token or not chat_id:
        raise ValueError("TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID are required")

    data = json.loads(Path("data/summarized.json").read_text())

    def load_stories(items):
        result = []
        for item in items:
            if isinstance(item.get("published_at"), str):
                item["published_at"] = datetime.fromisoformat(item["published_at"])
            result.append(Story(**item))
        return result

    top3 = load_stories(data["top3"])
    stories_by_category = {
        cat: load_stories(items)
        for cat, items in data["categories"].items()
    }

    week_of = datetime.now(tz=timezone.utc).strftime("%b %d, %Y")
    digest = format_digest(top3, stories_by_category, week_of=week_of)

    print(f"Digest length: {len(digest)} characters")
    asyncio.run(send_to_telegram(digest, bot_token, chat_id))
    print("Delivered to Telegram.")


if __name__ == "__main__":
    main()
```

**Step 5: Run all deliver tests**

```bash
pytest tests/pipeline/test_deliver.py -v
```

Expected: All tests PASS.

**Step 6: Run full test suite to catch regressions**

```bash
pytest tests/ -v --ignore=tests/scrapers
```

Expected: All tests PASS (scrapers skipped — they need live network).

**Step 7: Commit**

```bash
git add pipeline/deliver.py tests/pipeline/test_deliver.py
git commit -m "feat: HTML formatting, dedup top3 from categories, hide empty cats"
```

---

### Task 3: Final smoke check

**Step 1: Verify the full pipeline test passes**

```bash
pytest tests/test_smoke.py -v
```

Expected: PASS (or skip if it requires live credentials).

**Step 2: Confirm GitHub Actions workflow still references both pipeline steps**

```bash
grep -n "summarize\|deliver" .github/workflows/*.yml
```

Expected: Both steps present and in order.

**Step 3: Commit any final tweaks, then push**

```bash
git push origin master
```

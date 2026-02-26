"""
Job 5: Format stories and deliver to Telegram.

Format: Top 3 must-reads in full, then category digests.
No emoji. Professional tone.
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


def format_story_full(story: Story, index: int) -> str:
    sources_str = " | ".join(s.name for s in story.sources)
    if story.source_count > 1:
        sources_str += f" ({story.source_count} sources)"

    lines = [
        f"[{index}] {story.title}",
        f"Source: {sources_str} | Category: {CATEGORY_LABELS.get(story.priority_category, story.priority_category)}",
        "",
    ]

    if story.summary:
        lines += [
            f"What happened: {story.summary.what_happened}",
            f"Enterprise impact: {story.summary.enterprise_impact}",
            f"Software delivery impact: {story.summary.software_delivery_impact}",
            f"For developers: {story.summary.developer_impact}",
            f"For people: {story.summary.human_impact}",
            f"How to use it: {story.summary.how_to_use}",
            "",
        ]

    lines.append("Read more:")
    for src in story.sources:
        lines.append(f"  - {src.url}")

    return "\n".join(lines)


def format_story_brief(story: Story) -> str:
    impact = ""
    if story.summary:
        impact = f" — {story.summary.enterprise_impact[:80]}"
    return f"- {story.title}{impact}\n  {story.canonical_url}"


def format_digest(
    top3: list[Story],
    stories_by_category: dict[str, list[Story]],
    week_of: str,
) -> str:
    divider = "_" * 32
    sections = [
        f"AI DIGEST | Week of {week_of}",
        divider,
        "",
        "TOP 3 MUST-READS THIS WEEK",
        divider,
        "",
    ]

    for i, story in enumerate(top3, 1):
        sections.append(format_story_full(story, index=i))
        sections.append("")

    for cat, label in CATEGORY_LABELS.items():
        stories = stories_by_category.get(cat, [])
        sections += [divider, label, divider]
        if stories:
            for story in stories:
                sections.append(format_story_brief(story))
        else:
            sections.append("No significant stories this week.")
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
        # Split at last newline before limit
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

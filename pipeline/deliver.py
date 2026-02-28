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
        "<b>TOP 3 MUST-READS THIS WEEK</b>",
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

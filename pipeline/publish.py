"""
Publish: Write high-signal items to data/rdradar.json.

High-signal = SDLC tags contain at least one non-"general" tag.
Run after the pipeline completes; the workflow commits the output to the
'output' branch so that jarvis RDRadarModule can read it.
"""
import json
from datetime import datetime, timezone
from pathlib import Path

from schemas.story import Story

# SDLC tags that map to a recommended action
_ACTION_MAP = {
    "ai-agents": "spike",
    "delivery": "spike",
    "governance": "review",
    "tooling": "evaluate",
    "testing": "evaluate",
}


def _action_for_tags(tags: list[str]) -> str:
    """Derive a recommended action from SDLC tags (most-urgent wins)."""
    for tag in ("ai-agents", "delivery", "governance", "tooling", "testing"):
        if tag in tags:
            return _ACTION_MAP[tag]
    return "evaluate"


def _reason_for_story(story: Story) -> str:
    signal_tags = [t for t in story.sdlc_tags if t != "general"]
    tags_str = ", ".join(signal_tags) if signal_tags else "general"
    return f"Relevant to {tags_str} — assess for team adoption."


def build_rdradar(
    personal_items: list[Story],
    enterprise_items: list[Story],
) -> dict:
    """Build rdradar.json payload from high-signal items.

    Enterprise items are listed first; personal items fill in any gaps.
    Deduplication is by canonical URL.  Only stories with at least one
    non-'general' SDLC tag are included.
    """
    seen_urls: set[str] = set()
    items = []

    def _add(stories: list[Story], source: str) -> None:
        for story in stories:
            if story.canonical_url in seen_urls:
                continue
            signal_tags = [t for t in story.sdlc_tags if t != "general"]
            if not signal_tags:
                continue
            seen_urls.add(story.canonical_url)
            items.append({
                "title": story.title,
                "url": story.canonical_url,
                "sdlc_tags": signal_tags,
                "recommendation": {
                    "action": _action_for_tags(story.sdlc_tags),
                    "reason": _reason_for_story(story),
                },
                "source": source,
            })

    _add(enterprise_items, "enterprise")
    _add(personal_items, "personal")

    return {
        "generated_at": datetime.now(tz=timezone.utc).isoformat(),
        "items": items,
    }


def main() -> None:
    ranked_raw = json.loads(Path("data/ranked.json").read_text())

    def _load(items_raw: list[dict]) -> list[Story]:
        stories = []
        for item in items_raw:
            if isinstance(item.get("published_at"), str):
                item["published_at"] = datetime.fromisoformat(item["published_at"])
            stories.append(Story(**item))
        return stories

    personal_items = _load(ranked_raw.get("personal_items", []))
    enterprise_items = _load(ranked_raw.get("enterprise_items", []))

    payload = build_rdradar(personal_items, enterprise_items)
    Path("data").mkdir(exist_ok=True)
    Path("data/rdradar.json").write_text(json.dumps(payload, indent=2, default=str))
    print(f"  Saved {len(payload['items'])} high-signal items to data/rdradar.json")


if __name__ == "__main__":
    main()

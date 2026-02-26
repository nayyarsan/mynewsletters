"""
Job 2: Merge all raw JSON files, deduplicate stories.

Dedup strategy:
1. URL exact match — merge immediately, collect all source references
2. Title similarity — Jaccard token overlap >= threshold groups same story

Output: data/normalized.json (list of deduplicated Story objects)
"""
import json
import sys
from pathlib import Path
from datetime import datetime, timezone, timedelta
from schemas.story import Story, StorySource


def load_raw_stories(raw_dir: str = "data/raw") -> list[Story]:
    stories = []
    for path in Path(raw_dir).glob("*.json"):
        try:
            items = json.loads(path.read_text())
            for item in items:
                # Restore datetime from string
                if isinstance(item.get("published_at"), str):
                    item["published_at"] = datetime.fromisoformat(item["published_at"])
                stories.append(Story(**item))
        except Exception as e:
            print(f"  Warning: could not load {path}: {e}")
    return stories


def _title_tokens(title: str) -> set[str]:
    import re
    words = re.sub(r"[^\w\s]", "", title.lower()).split()
    stopwords = {"the", "a", "an", "is", "in", "on", "at", "to", "for", "of", "and", "or", "with"}
    return {w for w in words if w not in stopwords and len(w) > 2}


def _jaccard(a: set, b: set) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def deduplicate_by_url(stories: list[Story]) -> list[Story]:
    seen: dict[str, Story] = {}
    for story in stories:
        url = story.canonical_url
        if url in seen:
            existing = seen[url]
            # Merge sources, avoid duplicates
            existing_source_names = {s.name for s in existing.sources}
            for src in story.sources:
                if src.name not in existing_source_names:
                    existing.sources.append(src)
        else:
            seen[url] = story
    return list(seen.values())


def deduplicate_by_title_similarity(
    stories: list[Story],
    threshold: float = 0.6,
) -> list[Story]:
    groups: list[Story] = []
    for story in stories:
        tokens = _title_tokens(story.title)
        merged = False
        for canonical in groups:
            canonical_tokens = _title_tokens(canonical.title)
            if _jaccard(tokens, canonical_tokens) >= threshold:
                # Merge into canonical
                canonical_source_names = {s.name for s in canonical.sources}
                for src in story.sources:
                    if src.name not in canonical_source_names:
                        canonical.sources.append(src)
                merged = True
                break
        if not merged:
            groups.append(story)
    return groups


def filter_older_than_days(stories: list[Story], days: int = 7) -> list[Story]:
    cutoff = datetime.now(tz=timezone.utc) - timedelta(days=days)
    return [
        s for s in stories
        if s.published_at.replace(tzinfo=timezone.utc) >= cutoff
    ]


def normalize(raw_dir: str = "data/raw") -> list[Story]:
    stories = load_raw_stories(raw_dir)
    print(f"  Loaded {len(stories)} raw stories")

    stories = filter_older_than_days(stories, days=7)
    print(f"  After age filter: {len(stories)}")

    stories = deduplicate_by_url(stories)
    print(f"  After URL dedup: {len(stories)}")

    stories = deduplicate_by_title_similarity(stories, threshold=0.6)
    print(f"  After title similarity dedup: {len(stories)}")

    # Sort by source_count desc, then published_at desc
    stories.sort(key=lambda s: (s.source_count, s.published_at), reverse=True)
    return stories


def main():
    print("Normalizing stories...")
    stories = normalize()
    output = [s.model_dump(mode="json") for s in stories]
    Path("data/normalized.json").write_text(
        json.dumps(output, indent=2, default=str)
    )
    print(f"  Saved {len(stories)} normalized stories to data/normalized.json")


if __name__ == "__main__":
    main()

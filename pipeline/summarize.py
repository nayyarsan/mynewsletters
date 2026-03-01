"""
Job 4: Generate structured 6-dimension analysis for top-ranked stories.

Uses GitHub Models API (openai/gpt-4o) for higher quality summaries.
Only runs on top 3 stories to stay within rate limits (150 req/day).
Note: anthropic/claude-sonnet-4-6 is not available on GitHub Models API.
"""
import json
import os
from datetime import datetime, timezone, timedelta
from pathlib import Path
from openai import OpenAI
from schemas.story import Story, StorySummary
from pipeline.rank import get_client, CATEGORIES, recency_multiplier

SUMMARIZE_SYSTEM_PROMPT = """You are a senior enterprise AI analyst writing for technical
leaders and developers. Be concise, specific, and practical. Avoid hype and marketing language.
Write factual, actionable analysis. Return only valid JSON."""

SUMMARIZE_USER_PROMPT = """Analyze this AI news story and return a structured JSON analysis.

Title: {title}
Source: {sources}
Content: {content}

Return JSON only:
{{
  "what_happened": "2-3 sentence factual summary of the news",
  "enterprise_impact": "concrete and specific impact on enterprise organisations",
  "software_delivery_impact": "specific impact on how software is built and deployed",
  "developer_impact": "what developers should know or do differently",
  "human_impact": "broader societal and workforce implications",
  "how_to_use": "one actionable next step or experiment a team can try this week"
}}"""


CACHE_PATH = Path("data/summary_cache.json")
CACHE_MAX_DAYS = 14


def load_cache(path: Path = CACHE_PATH) -> dict:
    """Load summary cache, evicting entries older than CACHE_MAX_DAYS."""
    if not path.exists():
        return {}
    try:
        raw = json.loads(path.read_text())
        cutoff = datetime.now(tz=timezone.utc) - timedelta(days=CACHE_MAX_DAYS)
        return {
            url: entry for url, entry in raw.items()
            if datetime.fromisoformat(entry["cached_at"]) >= cutoff
        }
    except Exception:
        return {}


def save_cache(cache: dict, path: Path = CACHE_PATH) -> None:
    """Persist summary cache to disk."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(cache, indent=2))


def summarize_story(story: Story, client: OpenAI, cache: dict | None = None) -> Story:
    # Check cache first — skip LLM if we already have a summary for this URL
    if cache is not None and story.canonical_url in cache:
        print(f"  Cache hit: {story.title[:50]}")
        story.summary = StorySummary(**cache[story.canonical_url]["summary"])
        return story

    sources_str = " | ".join(s.name for s in story.sources)
    prompt = SUMMARIZE_USER_PROMPT.format(
        title=story.title,
        sources=sources_str,
        content=story.raw_content[:1500],
    )
    try:
        response = client.chat.completions.create(
            model="openai/gpt-4o",  # best available on GitHub Models API
            messages=[
                {"role": "system", "content": SUMMARIZE_SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            temperature=0.3,
            response_format={"type": "json_object"},
        )
        data = json.loads(response.choices[0].message.content)
        story.summary = StorySummary(**data)
        if cache is not None:
            cache[story.canonical_url] = {
                "summary": data,
                "cached_at": datetime.now(tz=timezone.utc).isoformat(),
            }
    except Exception as e:
        print(f"  Warning: summarize failed for '{story.title[:50]}': {e}")
    return story


def pick_top3(stories_by_category: dict[str, list[Story]]) -> list[Story]:
    all_stories = [s for stories in stories_by_category.values() for s in stories]
    all_stories.sort(
        key=lambda s: (
            (s.priority_score or 0) * recency_multiplier(s.published_at),
            s.source_count,
        ),
        reverse=True,
    )
    return all_stories[:3]


def main():
    client = get_client()
    cache = load_cache()
    print(f"  Loaded {len(cache)} cached summaries")

    ranked_raw = json.loads(Path("data/ranked.json").read_text())

    stories_by_category: dict[str, list[Story]] = {}
    for cat, items in ranked_raw.items():
        stories = []
        for item in items:
            if isinstance(item.get("published_at"), str):
                item["published_at"] = datetime.fromisoformat(item["published_at"])
            stories.append(Story(**item))
        stories_by_category[cat] = stories

    top3 = pick_top3(stories_by_category)
    print(f"Summarizing top 3 must-reads...")
    top3 = [summarize_story(s, client, cache) for s in top3]

    save_cache(cache)
    print(f"  Saved {len(cache)} summaries to cache")

    output = {
        "top3": [s.model_dump(mode="json") for s in top3],
        "categories": {
            cat: [s.model_dump(mode="json") for s in stories]
            for cat, stories in stories_by_category.items()
        },
    }
    Path("data/summarized.json").write_text(json.dumps(output, indent=2, default=str))
    print("  Saved to data/summarized.json")


if __name__ == "__main__":
    main()

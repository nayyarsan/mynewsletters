"""
Job 4: Generate structured 6-dimension analysis for top-ranked stories.

Uses GitHub Models API (openai/gpt-4o) for higher quality summaries.
Only runs on top 3 stories to stay within rate limits (150 req/day).
Note: anthropic/claude-sonnet-4-6 is not available on GitHub Models API.
"""
import json
from datetime import datetime, timezone, timedelta
from pathlib import Path
from openai import OpenAI
from schemas.story import Story, StorySummary
from pipeline.rank import get_client, recency_multiplier

SUMMARIZE_SYSTEM_PROMPT = """You are a senior enterprise AI analyst writing for technical
leaders and developers. Be concise, specific, and practical. Avoid hype and marketing language.
Write factual, actionable analysis. Return only valid JSON.

SPECIFICITY RULES (these override style preferences):
- Every field must contain at least one concrete noun: a product name, version
  number, company name, customer name, metric, dollar figure, or date.
- Reject generic verbs like "enables", "empowers", "leverages", "unlocks",
  "transforms", "revolutionizes". Use specific verbs that describe what the
  thing actually does (e.g. "indexes", "compiles", "throttles", "ships").
- If the source content does not give you a concrete detail for a field, write
  exactly: "Insufficient detail in source." — do NOT pad with vague language.
- Never repeat the title back as the summary."""

SUMMARIZE_USER_PROMPT = """Analyze this AI news story and return a structured JSON analysis.

Title: {title}
Source: {sources}
Published: {published_at} (today is {today})
Content: {content}

Return JSON only:
{{
  "what_happened": "2-3 sentence factual summary. Must name the product/version/company.",
  "enterprise_impact": "Concrete impact on enterprise orgs. Name the workflow, role, or system affected.",
  "software_delivery_impact": "Specific impact on how software is built/shipped. Name the SDLC stage or tool.",
  "developer_impact": "What developers should know or do differently. Be specific about the API, library, or technique.",
  "human_impact": "Broader societal/workforce implications. Cite the role, demographic, or measurable effect.",
  "how_to_use": "One actionable next step a team can try this week. Name the tool/command/integration.",
  "why_this_week": "One sentence: why does this matter NOW versus a month ago? (e.g. competitive timing, regulatory deadline, GA milestone, model price drop). If unclear, write 'Insufficient detail in source.'"
}}"""


# Bump filename when prompt or schema changes so stale entries don't poison fresh runs.
CACHE_PATH = Path("data/summary_cache_v2.json")
CACHE_MAX_DAYS = 14


def load_cache(path: Path = CACHE_PATH) -> dict:
    """Load summary cache, evicting entries older than CACHE_MAX_DAYS."""
    if not path.exists():
        return {}
    try:
        raw = json.loads(path.read_text())
        cutoff = datetime.now(tz=timezone.utc) - timedelta(days=CACHE_MAX_DAYS)
        result = {}
        for url, entry in raw.items():
            try:
                cached_at = datetime.fromisoformat(entry["cached_at"])
                # Treat naive timestamps as UTC (guards against manually-edited files)
                if cached_at.tzinfo is None:
                    cached_at = cached_at.replace(tzinfo=timezone.utc)
                if cached_at >= cutoff:
                    result[url] = entry
            except (KeyError, ValueError):
                pass  # skip malformed entries rather than discarding the whole cache
        return result
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
    today_iso = datetime.now(tz=timezone.utc).date().isoformat()
    published_iso = story.published_at.date().isoformat() if story.published_at else "unknown"
    prompt = SUMMARIZE_USER_PROMPT.format(
        title=story.title,
        sources=sources_str,
        published_at=published_iso,
        today=today_iso,
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

    # Build stories_by_category from flat personal_items list
    stories_by_category: dict[str, list[Story]] = {}
    for item in ranked_raw.get("personal_items", []):
        if isinstance(item.get("published_at"), str):
            item["published_at"] = datetime.fromisoformat(item["published_at"])
        story = Story(**item)
        cat = story.priority_category or "general_significance"
        stories_by_category.setdefault(cat, []).append(story)

    # Pass enterprise items through without re-summarising
    enterprise_items: list[Story] = []
    for item in ranked_raw.get("enterprise_items", []):
        if isinstance(item.get("published_at"), str):
            item["published_at"] = datetime.fromisoformat(item["published_at"])
        enterprise_items.append(Story(**item))

    top3 = pick_top3(stories_by_category)
    print("Summarizing top 3 must-reads...")
    top3 = [summarize_story(s, client, cache) for s in top3]

    save_cache(cache)
    print(f"  Saved {len(cache)} summaries to cache")

    output = {
        "top3": [s.model_dump(mode="json") for s in top3],
        "categories": {
            cat: [s.model_dump(mode="json") for s in stories]
            for cat, stories in stories_by_category.items()
        },
        "enterprise_items": [s.model_dump(mode="json") for s in enterprise_items],
    }
    Path("data/summarized.json").write_text(json.dumps(output, indent=2, default=str))
    print("  Saved to data/summarized.json")


if __name__ == "__main__":
    main()

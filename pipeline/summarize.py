"""
Job 4: Generate structured 6-dimension analysis for top-ranked stories.

Uses GitHub Models API (anthropic/claude-sonnet-4-6) for higher quality summaries.
1x premium multiplier — used only on top-ranked stories to minimise cost.
Only runs on top-ranked stories to manage token usage.
"""
import json
import os
from datetime import datetime
from pathlib import Path
from openai import OpenAI
from schemas.story import Story, StorySummary
from pipeline.rank import get_client, CATEGORIES

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


def summarize_story(story: Story, client: OpenAI) -> Story:
    sources_str = " | ".join(s.name for s in story.sources)
    prompt = SUMMARIZE_USER_PROMPT.format(
        title=story.title,
        sources=sources_str,
        content=story.raw_content[:1500],
    )
    try:
        response = client.chat.completions.create(
            model="claude-sonnet-4-6",              # 1x multiplier — premium quality
            messages=[
                {"role": "system", "content": SUMMARIZE_SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            temperature=0.3,
            response_format={"type": "json_object"},
        )
        data = json.loads(response.choices[0].message.content)
        story.summary = StorySummary(**data)
    except Exception as e:
        print(f"  Warning: summarize failed for '{story.title[:50]}': {e}")
    return story


def pick_top3(stories_by_category: dict[str, list[Story]]) -> list[Story]:
    all_stories = [
        s for stories in stories_by_category.values() for s in stories
    ]
    all_stories.sort(
        key=lambda s: (s.priority_score or 0, s.source_count),
        reverse=True,
    )
    return all_stories[:3]


def main():
    client = get_client()

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
    top3 = [summarize_story(s, client) for s in top3]

    print(f"Summarizing category stories...")
    for cat, stories in stories_by_category.items():
        stories_by_category[cat] = [summarize_story(s, client) for s in stories]

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

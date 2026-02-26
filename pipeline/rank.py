"""
Job 3: Score stories by enterprise relevance using GitHub Models API.

GitHub Models endpoint: https://models.github.ai/inference
Auth: GITHUB_TOKEN environment variable (uses your existing GitHub license)
Model: openai/gpt-4.1 (0x multiplier — completely free, no premium requests consumed)
"""
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from openai import OpenAI
from schemas.story import Story

RANK_SYSTEM_PROMPT = """You are an AI news curator for enterprise technology leaders.
Score news stories by enterprise relevance. Be strict — only score high if there is
clear, direct enterprise impact. Ignore pure academic research unless it has immediate
enterprise application. Return only valid JSON."""

RANK_USER_PROMPT = """Score this AI news story across 4 categories (0-100 each):
1. enterprise_software_delivery — AI in dev tools, coding agents, CI/CD, IDEs
2. enterprise_solutions — AI in ERP, CRM, business process automation
3. finance_utilities — AI in fintech, energy, regulated industries
4. general_significance — broad impact on developers and people

Title: {title}
Source: {source}
Content: {content}

Return JSON only:
{{"scores": {{"enterprise_software_delivery": 0, "enterprise_solutions": 0, "finance_utilities": 0, "general_significance": 0}}, "include": true}}"""

CATEGORIES = [
    "enterprise_software_delivery",
    "enterprise_solutions",
    "finance_utilities",
    "general_significance",
]


def get_client() -> OpenAI:
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        raise ValueError("GITHUB_TOKEN environment variable is required")
    return OpenAI(
        base_url="https://models.github.ai/inference",
        api_key=token,
    )


def rank_story(story: Story, client: OpenAI) -> Story | None:
    prompt = RANK_USER_PROMPT.format(
        title=story.title,
        source=story.sources[0].name if story.sources else "unknown",
        content=story.raw_content[:800],
    )
    try:
        response = client.chat.completions.create(
            model="openai/gpt-4.1",          # 0x multiplier — free
            messages=[
                {"role": "system", "content": RANK_SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            temperature=0,
            response_format={"type": "json_object"},
        )
        data = json.loads(response.choices[0].message.content)

        if not data.get("include", True):
            return None

        scores = data.get("scores", {})
        best_category = max(scores, key=lambda k: scores[k])
        best_score = scores[best_category]

        if best_score < 20:
            return None

        story.priority_category = best_category
        story.priority_score = best_score
        return story

    except Exception as e:
        print(f"  Warning: rank failed for '{story.title[:50]}': {e}")
        return None


def select_top_stories(
    stories: list[Story],
    per_category: int = 8,
) -> dict[str, list[Story]]:
    categorized: dict[str, list[Story]] = {c: [] for c in CATEGORIES}
    for story in stories:
        if story.priority_category and story.priority_category in categorized:
            categorized[story.priority_category].append(story)

    for cat in categorized:
        categorized[cat].sort(
            key=lambda s: (s.priority_score or 0, s.source_count),
            reverse=True,
        )
        categorized[cat] = categorized[cat][:per_category]

    return categorized


def main():
    client = get_client()

    stories_raw = json.loads(Path("data/normalized.json").read_text())
    stories = []
    for item in stories_raw:
        if isinstance(item.get("published_at"), str):
            item["published_at"] = datetime.fromisoformat(item["published_at"])
        stories.append(Story(**item))

    print(f"Ranking {len(stories)} stories...")
    ranked = []
    for i, story in enumerate(stories):
        result = rank_story(story, client)
        if result:
            ranked.append(result)
        if (i + 1) % 10 == 0:
            print(f"  Processed {i + 1}/{len(stories)}")

    print(f"  {len(ranked)} stories passed ranking filter")

    categorized = select_top_stories(ranked)
    total = sum(len(v) for v in categorized.values())
    print(f"  {total} stories selected across {len(CATEGORIES)} categories")

    output = {
        cat: [s.model_dump(mode="json") for s in cat_stories]
        for cat, cat_stories in categorized.items()
    }
    Path("data/ranked.json").write_text(json.dumps(output, indent=2, default=str))
    print("  Saved to data/ranked.json")


if __name__ == "__main__":
    main()

"""
Job 3: Score stories by enterprise relevance using GitHub Models API.

GitHub Models endpoint: https://models.github.ai/inference
Auth: GITHUB_TOKEN environment variable (uses your existing GitHub license)
Model: openai/gpt-4o-mini (Low tier: 150 req/day, 15 req/min — sufficient for scoring)
Summarize uses openai/gpt-4o (same tier as gpt-4o-mini — 150 req/day)

Rate limit optimisation (Low tier: 15 req/min, 150 req/day):
1. Heuristic pre-filter: cuts ~200 stories → 40 using source weight + source_count + keywords
2. Batch ranking: 5 stories per LLM call → ~8 calls total (was 200+ previously)
3. 5s delay between batches to stay within 15 req/min, with retry on 429
"""
import json
import os
import time
import yaml
from datetime import datetime, timezone, timedelta
from pathlib import Path
from openai import OpenAI
from schemas.story import Story

RANK_SYSTEM_PROMPT = """You are an AI news curator for enterprise technology leaders and developers.
Score news stories by enterprise relevance. Be strict — only score high if there is
clear, direct enterprise impact. Prefer original product announcements, release notes,
API changes, model launches, and technical research over vendor blog posts, listicles,
opinion pieces, or thought-leadership marketing content. Return only valid JSON."""

# Single-story prompt — kept for backwards compatibility and unit tests
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

# Batch prompt — scores up to 5 stories in a single LLM call
RANK_BATCH_PROMPT = """Score these {n} AI news stories across 4 categories (0-100 each):
1. enterprise_software_delivery — AI in dev tools, coding agents, CI/CD, IDEs
2. enterprise_solutions — AI in ERP, CRM, business process automation
3. finance_utilities — AI in fintech, energy, regulated industries
4. general_significance — broad impact on developers and people

{stories_text}
Return JSON only — one entry per story, 0-indexed:
{{"stories": [{{"index": 0, "scores": {{"enterprise_software_delivery": 0, "enterprise_solutions": 0, "finance_utilities": 0, "general_significance": 0}}, "include": true}}]}}"""

CATEGORIES = [
    "enterprise_software_delivery",
    "enterprise_solutions",
    "finance_utilities",
    "general_significance",
]

SDLC_TAGS = ["tooling", "testing", "delivery", "governance", "ai-agents", "general"]

SDLC_CLASSIFY_SYSTEM_PROMPT = """You are an AI news classifier for a software delivery knowledge base.
Classify news stories by SDLC (Software Development Lifecycle) category. Return only valid JSON."""

SDLC_CLASSIFY_BATCH_PROMPT = """For each story, return one or more tags from: tooling, testing, delivery, governance, ai-agents, general.
- tooling: new dev tools, IDEs, extensions
- testing: AI in QA, test generation, coverage
- delivery: CI/CD, deployment, release automation
- governance: AI policy, compliance, audit
- ai-agents: agent frameworks, MCP, orchestration
- general: everything else

{stories_text}
Return JSON only — one entry per story, 0-indexed:
{{"stories": [{{"index": 0, "title": "story title", "sdlc_tags": ["tooling", "ai-agents"]}}]}}\
"""

ENTERPRISE_KEYWORDS = {
    "enterprise", "agent", "agents", "copilot", "llm", "gpt", "claude", "gemini",
    "deploy", "deployment", "production", "api", "sdk", "model", "models",
    "automation", "workflow", "integration", "platform", "developer", "coding",
    "agentic", "inference", "fine-tuning", "finetuning", "rag", "mcp",
    "release", "launch", "announcement", "changelog", "update", "o1", "o3", "o4",
    "anthropic", "openai", "codex", "sonnet", "opus", "haiku",
}

_WEIGHT_SCORES = {"high": 20, "medium": 10, "low": 0}
PRESCORE_LIMIT = 40
BATCH_SIZE = 5


def recency_multiplier(published_at: datetime) -> float:
    """Return 1.0 for stories ≤7 days old, 0.5 for any older story."""
    pub = published_at if published_at.tzinfo else published_at.replace(tzinfo=timezone.utc)
    age_days = (datetime.now(tz=timezone.utc) - pub).days
    return 1.0 if age_days <= 7 else 0.5


def _load_source_weights() -> dict[str, int]:
    """Map source name → numeric weight from sources/sources.yaml."""
    try:
        data = yaml.safe_load(Path("sources/sources.yaml").read_text())
        return {
            s["name"]: _WEIGHT_SCORES.get(s.get("weight", "low"), 0)
            for s in data.get("sources", [])
        }
    except Exception:
        return {}


def heuristic_prescore(story: Story, source_weights: dict[str, int]) -> int:
    """Score a story without LLM using source weight, source_count, and keywords."""
    score = 0
    # Multi-source bonus: each extra source adds 10 pts, capped at +30
    score += min(story.source_count - 1, 3) * 10
    # Source weight bonus: sum across all sources the story appeared in
    for src in story.sources:
        score += source_weights.get(src.name, 0)
    # Keyword bonus: enterprise-relevant terms in the title
    title_words = set(story.title.lower().split())
    score += len(title_words & ENTERPRISE_KEYWORDS) * 5
    return int(score * recency_multiplier(story.published_at))


def presort_and_limit(
    stories: list[Story],
    source_weights: dict[str, int],
    limit: int = PRESCORE_LIMIT,
) -> list[Story]:
    """Sort by heuristic prescore and keep top N candidates for LLM ranking."""
    scored = sorted(
        stories,
        key=lambda s: heuristic_prescore(s, source_weights),
        reverse=True,
    )
    selected = scored[:limit]
    print(f"  Heuristic pre-filter: {len(selected)} of {len(stories)} stories kept")
    return selected


def get_client() -> OpenAI:
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        raise ValueError("GITHUB_TOKEN environment variable is required")
    return OpenAI(
        base_url="https://models.github.ai/inference",
        api_key=token,
    )


def rank_story(story: Story, client: OpenAI) -> Story | None:
    """Rank a single story. Kept for backwards compatibility and unit tests."""
    prompt = RANK_USER_PROMPT.format(
        title=story.title,
        source=story.sources[0].name if story.sources else "unknown",
        content=story.raw_content[:800],
    )
    try:
        response = client.chat.completions.create(
            model="openai/gpt-4o-mini",         # Low tier: 150 req/day, 15 req/min
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


def rank_batch(batch: list[Story], client: OpenAI, retries: int = 2) -> list[Story]:
    """Rank up to BATCH_SIZE stories in a single LLM call. Retries on 429 with backoff."""
    stories_text = ""
    for i, story in enumerate(batch):
        source = story.sources[0].name if story.sources else "unknown"
        stories_text += (
            f"\nStory {i} — Title: {story.title}\n"
            f"  Source: {source}\n"
            f"  Content: {story.raw_content[:400]}\n"
        )

    prompt = RANK_BATCH_PROMPT.format(n=len(batch), stories_text=stories_text)

    for attempt in range(retries + 1):
        try:
            response = client.chat.completions.create(
                model="openai/gpt-4o-mini",         # Low tier: 150 req/day, 15 req/min
                messages=[
                    {"role": "system", "content": RANK_SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
                temperature=0,
                response_format={"type": "json_object"},
            )
            data = json.loads(response.choices[0].message.content)
            results = data.get("stories", [])

            ranked = []
            for item in results:
                idx = item.get("index", -1)
                if not isinstance(idx, int) or idx < 0 or idx >= len(batch):
                    continue
                if not item.get("include", True):
                    continue
                scores = item.get("scores", {})
                if not scores:
                    continue
                best_category = max(scores, key=lambda k: scores[k])
                best_score = scores[best_category]
                if best_score < 20:
                    continue
                story = batch[idx]
                story.priority_category = best_category
                story.priority_score = best_score
                ranked.append(story)

            return ranked

        except Exception as e:
            is_rate_limit = "429" in str(e) or "Too many requests" in str(e)
            if is_rate_limit and attempt < retries:
                wait = 15 * (attempt + 1)   # 15s, then 30s
                print(f"  Rate limited — waiting {wait}s before retry {attempt + 1}/{retries}")
                time.sleep(wait)
            else:
                print(f"  Warning: batch rank failed: {e}")
                return []

    return []


def classify_sdlc_tags(stories: list[Story], client: OpenAI) -> list[Story]:
    """Classify each ranked story with SDLC tags using batched LLM calls.

    Processes BATCH_SIZE stories per call, same rate-limit pattern as rank_batch().
    Falls back to ["general"] for any story whose tags cannot be determined.
    """
    total_batches = (len(stories) + BATCH_SIZE - 1) // BATCH_SIZE
    print(f"Classifying SDLC tags for {len(stories)} stories in {total_batches} batches of {BATCH_SIZE}...")

    # Build an index map so we can update stories in-place
    story_index: dict[int, Story] = {}
    for i, story in enumerate(stories):
        story_index[i] = story

    for batch_start in range(0, len(stories), BATCH_SIZE):
        if batch_start > 0:
            time.sleep(5)   # stay within 15 req/min limit

        batch = stories[batch_start:batch_start + BATCH_SIZE]
        stories_text = ""
        for j, story in enumerate(batch):
            stories_text += (
                f"\nStory {j} — Title: {story.title}\n"
                f"  Content: {story.raw_content[:400]}\n"
            )

        prompt = SDLC_CLASSIFY_BATCH_PROMPT.format(stories_text=stories_text)
        batch_num = batch_start // BATCH_SIZE + 1

        try:
            response = client.chat.completions.create(
                model="openai/gpt-4o-mini",
                messages=[
                    {"role": "system", "content": SDLC_CLASSIFY_SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
                temperature=0,
                response_format={"type": "json_object"},
            )
            data = json.loads(response.choices[0].message.content)
            results = data.get("stories", [])

            tagged_indices = set()
            for item in results:
                idx = item.get("index", -1)
                if not isinstance(idx, int) or idx < 0 or idx >= len(batch):
                    continue
                raw_tags = item.get("sdlc_tags", [])
                valid_tags = [t for t in raw_tags if t in SDLC_TAGS]
                batch[idx].sdlc_tags = valid_tags if valid_tags else ["general"]
                tagged_indices.add(idx)

            # Fallback for any story the LLM didn't return
            for j in range(len(batch)):
                if j not in tagged_indices:
                    batch[j].sdlc_tags = ["general"]

            print(f"  SDLC batch {batch_num}/{total_batches}: {len(tagged_indices)}/{len(batch)} classified")

        except Exception as e:
            print(f"  Warning: SDLC classification failed for batch {batch_num}: {e}")
            for story in batch:
                if not story.sdlc_tags:
                    story.sdlc_tags = ["general"]

    # Final safety net — ensure every story has at least one tag
    for story in stories:
        if not story.sdlc_tags:
            story.sdlc_tags = ["general"]

    return stories


def select_top_stories(
    stories: list[Story],
    per_category: int = 5,
) -> dict[str, list[Story]]:
    categorized: dict[str, list[Story]] = {c: [] for c in CATEGORIES}
    for story in stories:
        if story.priority_category and story.priority_category in categorized:
            categorized[story.priority_category].append(story)

    for cat in categorized:
        categorized[cat].sort(
            key=lambda s: (
                (s.priority_score or 0) * recency_multiplier(s.published_at),
                s.source_count,
            ),
            reverse=True,
        )
        categorized[cat] = categorized[cat][:per_category]

    return categorized


def main():
    client = get_client()
    source_weights = _load_source_weights()

    stories_raw = json.loads(Path("data/normalized.json").read_text())
    stories = []
    for item in stories_raw:
        if isinstance(item.get("published_at"), str):
            item["published_at"] = datetime.fromisoformat(item["published_at"])
        stories.append(Story(**item))

    # Drop stories older than 14 days — prevents repeat stories across weeks
    cutoff = datetime.now(tz=timezone.utc) - timedelta(days=14)
    before = len(stories)
    stories = [
        s for s in stories
        if (s.published_at if s.published_at.tzinfo else s.published_at.replace(tzinfo=timezone.utc)) >= cutoff
    ]
    print(f"  Recency filter: {before - len(stories)} stories dropped (>14 days), {len(stories)} remain")

    # Step 1: heuristic pre-filter — no LLM calls
    stories = presort_and_limit(stories, source_weights, limit=PRESCORE_LIMIT)

    # Step 2: batch LLM ranking — BATCH_SIZE stories per call
    total_batches = (len(stories) + BATCH_SIZE - 1) // BATCH_SIZE
    print(f"Ranking {len(stories)} stories in {total_batches} batches of {BATCH_SIZE}...")
    ranked = []
    for i in range(0, len(stories), BATCH_SIZE):
        if i > 0:
            time.sleep(5)   # 5s gap → ~12 req/min, under the 15 req/min limit
        batch = stories[i:i + BATCH_SIZE]
        results = rank_batch(batch, client)
        ranked.extend(results)
        batch_num = i // BATCH_SIZE + 1
        print(f"  Batch {batch_num}/{total_batches}: {len(results)}/{len(batch)} ranked")

    print(f"  {len(ranked)} stories passed ranking filter")

    # Step 3: classify SDLC tags — BATCH_SIZE stories per call
    ranked = classify_sdlc_tags(ranked, client)

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

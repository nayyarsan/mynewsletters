"""
Local smoke-test for rank + summarize against the real GitHub Models API.

Uses gpt-4o-mini (rank) + gpt-4o (summarize) — both broadly accessible
with a standard PAT. Production Actions uses gpt-4.1 + claude-sonnet-4-6
via the GITHUB_TOKEN with models:read permission.

Usage (PowerShell):
    $env:GITHUB_TOKEN = "your-pat-here"
    python scripts/test_llm_local.py
"""
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

# Load .env from project root if it exists
_env_file = Path(__file__).parent.parent / ".env"
if _env_file.exists():
    for line in _env_file.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, _, value = line.partition("=")
            os.environ.setdefault(key.strip(), value.strip())

from openai import OpenAI
from schemas.story import Story
from pipeline.rank import (
    RANK_SYSTEM_PROMPT, RANK_BATCH_PROMPT, CATEGORIES,
    heuristic_prescore, presort_and_limit, select_top_stories,
)
from pipeline.summarize import SUMMARIZE_SYSTEM_PROMPT, SUMMARIZE_USER_PROMPT

# Local-only models — accessible with a standard PAT
RANK_MODEL = "openai/gpt-4o-mini"
SUMMARIZE_MODEL = "openai/gpt-4o"

SYNTHETIC_STORIES = [
    {
        "title": "GitHub Copilot gains agentic code review capabilities",
        "url": "https://github.blog/2026-02-copilot-agentic-review",
        "source": "github_blog",
        "content": "GitHub announced that Copilot can now autonomously review pull requests, suggest fixes, and open follow-up PRs. The feature is in public beta for GitHub Enterprise customers and integrates with existing CI/CD pipelines.",
    },
    {
        "title": "Anthropic releases Claude 4 with extended context window",
        "url": "https://anthropic.com/claude-4",
        "source": "anthropic",
        "content": "Anthropic today released Claude 4, featuring a 1 million token context window and improved reasoning on multi-step enterprise tasks. The model is available via API with enterprise tier pricing.",
    },
    {
        "title": "OpenAI launches GPT-5 enterprise API with fine-tuning",
        "url": "https://openai.com/gpt-5-enterprise",
        "source": "openai",
        "content": "OpenAI's GPT-5 is now available with enterprise fine-tuning support, allowing companies to customise the model on proprietary data while keeping it within their security perimeter.",
    },
    {
        "title": "SAP integrates Joule AI into all ERP workflows",
        "url": "https://news.sap.com/joule-erp-2026",
        "source": "sap_ai",
        "content": "SAP has embedded its Joule AI assistant into procurement, finance, and HR modules. Enterprise customers can now automate approval workflows and generate reports using natural language.",
    },
    {
        "title": "NVIDIA releases inference optimised H200 for on-prem LLM deployment",
        "url": "https://blogs.nvidia.com/h200-inference",
        "source": "nvidia_ai",
        "content": "NVIDIA's new H200 GPU delivers 4x throughput improvement for LLM inference compared to H100. Targeted at enterprises running private models, it ships with NVIDIA Inference Microservices (NIM).",
    },
    {
        "title": "LangChain releases LangGraph 2.0 for production agent orchestration",
        "url": "https://blog.langchain.dev/langgraph-2",
        "source": "langchain",
        "content": "LangGraph 2.0 introduces durable execution, human-in-the-loop checkpoints, and native support for multi-agent coordination. The release targets teams moving from prototype to production AI agents.",
    },
]


def build_stories() -> list[Story]:
    return [
        Story.from_url(
            url=s["url"],
            title=s["title"],
            source_name=s["source"],
            published_at=datetime(2026, 2, 24, tzinfo=timezone.utc),
            raw_content=s["content"],
        )
        for s in SYNTHETIC_STORIES
    ]


def rank_batch_local(batch: list[Story], client: OpenAI) -> list[Story]:
    stories_text = "".join(
        f"\nStory {i} — Title: {s.title}\n"
        f"  Source: {s.sources[0].name if s.sources else 'unknown'}\n"
        f"  Content: {s.raw_content[:400]}\n"
        for i, s in enumerate(batch)
    )
    prompt = RANK_BATCH_PROMPT.format(n=len(batch), stories_text=stories_text)
    response = client.chat.completions.create(
        model=RANK_MODEL,
        messages=[
            {"role": "system", "content": RANK_SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        temperature=0,
        response_format={"type": "json_object"},
    )
    data = json.loads(response.choices[0].message.content)
    ranked = []
    for item in data.get("stories", []):
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


def summarize_story_local(story: Story, client: OpenAI) -> Story:
    from schemas.story import StorySummary
    sources_str = " | ".join(s.name for s in story.sources)
    prompt = SUMMARIZE_USER_PROMPT.format(
        title=story.title,
        sources=sources_str,
        content=story.raw_content[:1500],
    )
    response = client.chat.completions.create(
        model=SUMMARIZE_MODEL,
        messages=[
            {"role": "system", "content": SUMMARIZE_SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        temperature=0.3,
        response_format={"type": "json_object"},
    )
    data = json.loads(response.choices[0].message.content)
    story.summary = StorySummary(**data)
    return story


def main():
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        print("ERROR: GITHUB_TOKEN is not set.")
        print("  PowerShell: $env:GITHUB_TOKEN = 'your-token'")
        sys.exit(1)

    client = OpenAI(
        base_url="https://models.github.ai/inference",
        api_key=token,
    )

    stories = build_stories()
    print(f"Built {len(stories)} synthetic stories")

    # --- Rank ---
    print(f"\n--- Rank (model: {RANK_MODEL}) ---")
    source_weights = {"github_blog": 20, "anthropic": 20, "openai": 20,
                      "sap_ai": 10, "nvidia_ai": 10, "langchain": 10}
    stories = presort_and_limit(stories, source_weights, limit=40)

    ranked = []
    batch_size = 5
    for i in range(0, len(stories), batch_size):
        batch = stories[i:i + batch_size]
        try:
            results = rank_batch_local(batch, client)
            ranked.extend(results)
            print(f"  Batch {i//batch_size + 1}: {len(results)}/{len(batch)} ranked")
        except Exception as e:
            print(f"  Batch {i//batch_size + 1} failed: {e}")

    categorized = select_top_stories(ranked)
    total = sum(len(v) for v in categorized.values())
    print(f"\nRanked: {total} stories across {len(CATEGORIES)} categories")
    for cat, items in categorized.items():
        if items:
            print(f"  {cat}:")
            for s in items:
                print(f"    [{s.priority_score}] {s.title[:65]}")

    if total == 0:
        print("\nERROR: No stories ranked. Check token scope and model access.")
        sys.exit(1)

    # Save ranked.json (same format as production)
    Path("data").mkdir(exist_ok=True)
    ranked_output = {
        cat: [s.model_dump(mode="json") for s in items]
        for cat, items in categorized.items()
    }
    Path("data/ranked.json").write_text(json.dumps(ranked_output, indent=2, default=str))
    print("  Saved data/ranked.json")

    # --- Summarize top story only (saves API calls) ---
    all_ranked = [s for items in categorized.values() for s in items]
    all_ranked.sort(key=lambda s: (s.priority_score or 0, s.source_count), reverse=True)
    top1 = all_ranked[:1]

    print(f"\n--- Summarize top story (model: {SUMMARIZE_MODEL}) ---")
    for story in top1:
        try:
            story = summarize_story_local(story, client)
            print(f"  Title: {story.title}")
            if story.summary:
                print(f"  What happened: {story.summary.what_happened}")
                print(f"  Enterprise impact: {story.summary.enterprise_impact}")
                print(f"  How to use: {story.summary.how_to_use}")
            else:
                print("  WARNING: no summary generated")
        except Exception as e:
            print(f"  Summarize failed: {e}")
            sys.exit(1)

    print("\nLocal LLM test passed.")


if __name__ == "__main__":
    main()

# AI Newsletter Agent

A fully automated weekly AI digest delivered to Telegram. Fetches stories from 35 curated sources, ranks them with an LLM, generates structured analysis for the top picks, and formats a clean digest with Telegram HTML formatting.

Runs every Monday at 6am UTC via GitHub Actions.

## Pipeline

```
validate → fetch → normalize → rank → summarize → deliver
```

| Step | What it does |
|------|-------------|
| `validate_feeds.py` | Checks all sources in `sources/sources.yaml` are reachable |
| `fetch.py` | Fetches stories from RSS feeds, scraped pages, APIs, and Reddit |
| `normalize.py` | Deduplicates by URL and Jaccard title similarity |
| `rank.py` | Heuristic pre-filter + LLM batch ranking (gpt-4o-mini) |
| `summarize.py` | 6-dimension analysis of the top 3 stories (gpt-4o); caches results by URL |
| `deliver.py` | Formats digest as Telegram HTML and sends via bot |

## Sources

35 sources across 4 categories:
- **Enterprise Software Delivery** — VS Code, GitHub Copilot, JetBrains, etc.
- **Enterprise Solutions** — AWS, Azure, GCP AI services
- **Finance & Utilities** — Bloomberg, FT AI coverage
- **General Significance** — Simon Willison, Hacker News, TLDR AI, Reddit

## Output Format

```
AI DIGEST | Week of Feb 28, 2026

TOP 3 MUST-READS THIS WEEK

1. Story title
   Source · Category

   What happened: ...
   Enterprise impact: ...
   For developers: ...
   How to use it: ...

   🔗 Read more

────────────────────────────────
ENTERPRISE SOFTWARE DELIVERY

• Story title
• Story title
```

## Setup

### Prerequisites

- Python 3.12+
- A Telegram bot token and chat ID
- A GitHub personal access token with `models:read` permission

### Local development

```bash
# Install dependencies
pip install -r requirements-dev.txt

# Create .env at project root
cp .env.example .env
# Fill in GITHUB_TOKEN, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID

# Run tests
pytest tests/ --ignore=tests/scrapers

# Run a single pipeline step manually
PYTHONPATH=. python pipeline/fetch.py
```

### GitHub Actions

The workflow runs automatically every Monday. To run manually:
1. Go to **Actions** → **AI Newsletter** → **Run workflow**

Required repository secrets:
- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHAT_ID`

The workflow uses `GITHUB_TOKEN` (auto-provided) for the GitHub Models API — no extra secret needed, but the token requires `models: read` permission (set in the workflow).

## Rate Limits (GitHub Models API)

| Model | Tier | Limit | Used for |
|-------|------|-------|----------|
| `gpt-4o-mini` | Low | 150 req/day, 15 req/min | Ranking |
| `gpt-4o` | Low | 150 req/day, 15 req/min | Summarizing (top 3 stories) |

Note: Anthropic/Claude models are not available on the GitHub Models API. Both models above are OpenAI via `models.github.ai/inference`.

## Recency Filtering

Stories are filtered before ranking:
- **14-day hard cutoff** — stories older than 14 days are dropped entirely
- **Recency decay** — stories 8–14 days old score at 0.5× in all ranking stages, so fresh stories always beat equally-scored stale ones

## Summary Cache

Summaries are cached in `data/summary_cache.json` (persisted between GitHub Actions runs via `actions/cache`). If a story URL was already summarized in a previous run, the cached result is reused — no LLM call needed. Cache entries are evicted after 14 days.

## Project Structure

```
pipeline/          # One Python module per pipeline step
schemas/           # Pydantic models (Story, StorySummary, StorySource)
scrapers/          # Feed fetchers (RSS, HTML scrape, API, Reddit)
sources/           # sources.yaml — all 35 source definitions
tests/             # pytest test suite
docs/plans/        # Design docs and implementation plans
.github/workflows/ # GitHub Actions workflow
```

## License

MIT

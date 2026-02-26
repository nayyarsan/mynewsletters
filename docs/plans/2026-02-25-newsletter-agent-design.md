# AI Newsletter Agent — Design Document
**Date:** 2026-02-25
**Status:** Approved
**Author:** Design session with Claude Code

---

## Overview

A fully automated weekly AI news digest that collects content from 35 curated sources, ranks and summarises stories using an LLM, deduplicates cross-source coverage, and delivers a structured professional digest to Telegram. Runs entirely on GitHub Actions using an existing GitHub license (no additional infrastructure cost).

---

## Goals

- Deliver a weekly digest of AI news filtered and ranked by enterprise relevance
- Cover AI-first IDEs, enterprise solutions, finance/utilities, and general developer significance
- Deduplicate stories appearing across multiple sources, surfacing cross-source signal as a ranking boost
- Run automatically with zero manual intervention
- Be fully configurable — add or remove sources without touching code

---

## Non-Goals (v1)

- Real-time or daily delivery (weekly only in v1)
- Audio podcast delivery (Phase 2)
- Email/Gmail delivery (Phase 2)
- WhatsApp delivery (Phase 2)
- Web UI or searchable archive (Phase 2)

---

## Priority Categories

Stories are ranked and grouped into four categories, in priority order:

1. **Enterprise Software Delivery** — AI in dev tools, coding agents, CI/CD, IDEs
2. **Enterprise Solutions** — AI in ERP, CRM, business process automation
3. **Finance & Utilities** — AI in fintech, energy, regulated industries
4. **General Significance** — broad impact on developers and people

---

## Architecture

### Pipeline Overview

```
GitHub Actions (Weekly Cron — Monday 6am UTC)
        |
        v
Job 0: VALIDATE       — test all feeds, mark dead sources as skipped
        |
        v
Job 1: FETCH          — parallel matrix job, one runner per source
   (35 sources)         RSS / scrape / API → raw JSON per source
        |
        v artifacts
Job 2: NORMALIZE      — merge all raws, deduplicate, build canonical stories
        |
        v artifacts
Job 3: RANK           — GitHub Models API scores each story 0-100 per category
        |
        v artifacts
Job 4: SUMMARIZE      — GitHub Models API generates 6-dimension analysis per story
        |
        v artifacts
Job 5: DELIVER        — format and send to Telegram
```

### Technology Stack

| Concern | Tool |
|---|---|
| Language | Python 3.12 |
| RSS parsing | feedparser |
| Web scraping | httpx + BeautifulSoup4 |
| Data validation | Pydantic |
| LLM (rank + summarise) | OpenAI SDK → GitHub Models API (`models.inference.ai.azure.com`) |
| LLM auth | `GITHUB_TOKEN` (built-in, uses existing GitHub license) |
| Delivery | python-telegram-bot |
| Config | PyYAML |
| Scheduling + orchestration | GitHub Actions |

### Secrets

| Secret | Source |
|---|---|
| `GITHUB_TOKEN` | Built-in to GitHub Actions, no setup needed |
| `TELEGRAM_BOT_TOKEN` | Create bot via @BotFather on Telegram |
| `TELEGRAM_CHAT_ID` | Get from @userinfobot on Telegram |

---

## Sources (Locked)

### RSS Sources (23)

| Source | URL | Weight |
|---|---|---|
| Andrej Karpathy | https://karpathy.github.io/feed.xml | high |
| Demis Hassabis (DeepMind) | https://deepmind.google/blog/rss.xml | high |
| Meta Engineering (Yann LeCun) | https://engineering.fb.com/feed/ | high |
| GitHub Blog (AI) | https://github.blog/feed/ | high |
| GitHub Copilot Changelog | https://github.blog/changelog/feed/ | high |
| VS Code | https://code.visualstudio.com/feed.xml | high |
| OpenAI | https://openai.com/news/rss.xml | high |
| Google DeepMind | https://deepmind.google/blog/rss.xml | high |
| Microsoft AI | https://blogs.microsoft.com/ai/feed/ | high |
| Windsurf (Codeium) | https://codeium.com/feed.xml | high |
| Hugging Face | https://huggingface.co/blog/feed.xml | medium |
| Salesforce AI | https://www.salesforce.com/blog/category/ai/feed/ | medium |
| Import AI (Jack Clark) | https://jack-clark.net/feed/ | medium |
| Latent Space | https://www.latent.space/feed | medium |
| Simon Willison | https://simonwillison.net/atom/everything/ | medium |
| KDNuggets | https://www.kdnuggets.com/feed | medium |
| Towards Data Science | https://towardsdatascience.com/feed | medium |
| SAP AI | https://news.sap.com/feed/ | medium |
| Azure AI | https://azure.microsoft.com/en-us/blog/feed/ | medium |
| LangChain | https://blog.langchain.dev/rss/ | medium |
| NVIDIA AI Blog | https://blogs.nvidia.com/feed/ | medium |
| AWS Machine Learning | https://aws.amazon.com/blogs/machine-learning/feed/ | medium |
| Lex Fridman Podcast | https://lexfridman.com/feed/podcast/ | low |

### Scrape Sources (7)

| Source | URL | Weight |
|---|---|---|
| Andrew Ng (The Batch) | https://www.deeplearning.ai/the-batch/ | high |
| Anthropic | https://www.anthropic.com/news | high |
| Cognition (Devin) | https://cognition.ai/blog | high |
| Cursor | https://www.cursor.com/blog | high |
| Thinking Machines (Mira Murati) | https://www.thinkingmachines.ai/blog | high |
| Mistral AI | https://mistral.ai/news/ | medium |
| TLDR AI | https://tldr.tech/ai | medium |

### API Sources (1)

| Source | URL | Weight |
|---|---|---|
| Hacker News AI | https://hn.algolia.com/api/v1/search?tags=story&query=AI+enterprise&hitsPerPage=30 | medium |

### Reddit RSS Sources (4)

| Source | URL | Weight |
|---|---|---|
| r/AINews | https://www.reddit.com/r/AINews/top/.rss?t=week | medium |
| r/promptengineering | https://www.reddit.com/r/promptengineering/top/.rss?t=week | medium |
| r/LLMDevs | https://www.reddit.com/r/LLMDevs/top/.rss?t=week | medium |
| r/ClaudeAI | https://www.reddit.com/r/ClaudeAI/top/.rss?t=week | medium |

### Dropped Sources (blocked or no feed available)

- ServiceNow AI — HTTP 403, blocks all bots
- Replit — HTTP 403, blocks all feed requests
- xAI Blog — HTTP 403, blocks all access

---

## Data Schema

### Normalized Story

```json
{
  "id": "sha256-of-canonical-url",
  "title": "Story headline",
  "canonical_url": "https://...",
  "sources": [
    {"name": "OpenAI", "url": "https://openai.com/..."},
    {"name": "Hacker News", "url": "https://news.ycombinator.com/..."}
  ],
  "source_count": 2,
  "published_at": "2026-02-24T10:00:00Z",
  "raw_content": "Full text or description...",
  "priority_category": null,
  "priority_score": null,
  "summary": {
    "what_happened": null,
    "enterprise_impact": null,
    "software_delivery_impact": null,
    "developer_impact": null,
    "human_impact": null,
    "how_to_use": null
  }
}
```

---

## Deduplication

Handled in the normalize step, two passes:

1. **URL exact match** — identical URLs merged immediately
2. **Semantic similarity** — LLM-based title grouping for same story from different sources

Merged stories retain all source references. `source_count > 1` applies a ranking boost — a story covered by multiple sources signals broader industry significance.

---

## LLM Prompts

### Rank Prompt (per story, lightweight)

```
SYSTEM: You are an AI news curator. Score stories for enterprise relevance only.
Ignore pure academic research unless it has clear, direct enterprise application.

USER: Score this story across 4 categories (0-100 each):
1. enterprise_software_delivery
2. enterprise_solutions
3. finance_utilities
4. general_significance

Title: {title}
Content: {raw_content}

Return JSON only:
{"scores": {"enterprise_software_delivery": 0, ...}, "include": true}
```

### Summarize Prompt (top-ranked stories only)

```
SYSTEM: You are a senior enterprise AI analyst. Be concise, specific, and practical.
Avoid hype. Write for technical leaders and developers.

USER: Analyze this story and return structured JSON:

Title: {title}
Source: {source}
Content: {raw_content}

Return JSON only:
{
  "what_happened": "2-3 sentence factual summary",
  "enterprise_impact": "concrete impact on enterprise organisations",
  "software_delivery_impact": "specific impact on how software is built and deployed",
  "developer_impact": "what developers should know or do",
  "human_impact": "broader societal and workforce implications",
  "how_to_use": "actionable next step or experiment to try"
}
```

---

## Delivery Format (Telegram)

```
AI DIGEST | Week of [DATE]
________________________________

TOP 3 MUST-READS THIS WEEK
________________________________

[1] STORY TITLE
Source: OpenAI | Hacker News (2 sources) | Category: Enterprise Software Delivery

What happened: ...
Enterprise impact: ...
Software delivery impact: ...
For developers: ...
For people: ...
How to use it: ...

Read more:
  - https://openai.com/...
  - https://news.ycombinator.com/...

[2] ...
[3] ...

________________________________
ENTERPRISE SOFTWARE DELIVERY
________________________________
- Story title — one-line impact
  https://...

________________________________
ENTERPRISE SOLUTIONS
________________________________
- ...

________________________________
FINANCE & UTILITIES
________________________________
- ...

________________________________
GENERAL SIGNIFICANCE
________________________________
- ...
```

---

## GitHub Actions Workflow

**Schedule:** Every Monday 6am UTC (`cron: '0 6 * * 1'`)
**Manual trigger:** `workflow_dispatch` for testing

**Estimated runtime per run:** ~22 minutes
**Monthly usage (4 runs):** ~88 minutes of 3000 available

| Job | Depends on | Runs on |
|---|---|---|
| validate | — | ubuntu-latest |
| fetch (matrix, 35 parallel) | validate | ubuntu-latest |
| normalize | fetch | ubuntu-latest |
| rank | normalize | ubuntu-latest |
| summarize | rank | ubuntu-latest |
| deliver | summarize | ubuntu-latest |

Data passed between jobs as GitHub Actions artifacts (JSON files).

---

## Project Structure

```
newsletteragent/
├── .github/
│   └── workflows/
│       └── newsletter.yml
├── sources/
│   └── sources.yaml
├── pipeline/
│   ├── validate_feeds.py
│   ├── fetch.py
│   ├── normalize.py
│   ├── rank.py
│   ├── summarize.py
│   └── deliver.py
├── scrapers/
│   ├── rss.py
│   ├── html.py
│   └── api.py
├── schemas/
│   └── story.py
├── requirements.txt
└── docs/
    └── plans/
        └── 2026-02-25-newsletter-agent-design.md
```

---

## Phase 2 Roadmap

| Capability | Approach |
|---|---|
| Podcast (TTS audio) | `edge-tts` (free, no API key) → MP3 → Telegram audio message |
| Email delivery | Resend API (free tier) + Jinja2 HTML template |
| WhatsApp delivery | WhatsApp Business API or Twilio |
| Daily lightweight digest | Second cron + `--mode daily` flag |
| Searchable archive | Commit `summarized.json` weekly to repo |
| Web UI | GitHub Pages rendered from committed JSONs |

---

## Open Items

- Scraper implementations for 7 scrape-only sources need individual testing
- Anthropic RSS not publicly available — scraper must handle JavaScript-rendered content
- Reddit rate limits: add `User-Agent` header and 0.5s delay between requests
- GitHub Models API model selection: default to `gpt-4o-mini` for rank (cost), `gpt-4o` for summarize (quality)

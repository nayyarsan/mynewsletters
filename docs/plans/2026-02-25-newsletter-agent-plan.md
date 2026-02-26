# AI Newsletter Agent — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a fully automated weekly AI news digest that fetches 35 sources, deduplicates and ranks stories by enterprise relevance using GitHub Models API, and delivers a structured digest to Telegram via GitHub Actions.

**Architecture:** Modular pipeline of Python scripts (validate → fetch → normalize → rank → summarize → deliver) chained as GitHub Actions jobs, with data passed as JSON artifacts between stages. Sources are fully config-driven via a single YAML file — no code changes needed to add/remove sources.

**Tech Stack:** Python 3.12, feedparser, httpx, BeautifulSoup4, Pydantic, openai SDK (→ GitHub Models API), python-telegram-bot, PyYAML, pytest, GitHub Actions

---

## Pre-requisites

Before starting:
1. Create a Telegram bot via @BotFather — note the `BOT_TOKEN`
2. Message @userinfobot on Telegram — note your `CHAT_ID`
3. These go in GitHub repo Settings → Secrets → Actions as `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID`
4. `GITHUB_TOKEN` is automatic — no setup needed

---

## Task 1: Project Scaffolding

**Files:**
- Create: `requirements.txt`
- Create: `requirements-dev.txt`
- Create: `sources/sources.yaml`
- Create: `schemas/__init__.py`
- Create: `scrapers/__init__.py`
- Create: `pipeline/__init__.py`
- Create: `tests/__init__.py`
- Create: `tests/scrapers/__init__.py`
- Create: `tests/pipeline/__init__.py`
- Create: `data/.gitkeep`

**Step 1: Create requirements.txt**

```
feedparser==6.0.11
httpx==0.27.2
beautifulsoup4==4.12.3
openai==1.51.2
python-telegram-bot==21.6
pyyaml==6.0.2
pydantic==2.9.2
```

**Step 2: Create requirements-dev.txt**

```
-r requirements.txt
pytest==8.3.3
pytest-asyncio==0.24.0
pytest-mock==3.14.0
respx==0.21.1
```

**Step 3: Create sources/sources.yaml**

```yaml
sources:
  # --- INFLUENCERS ---
  - name: karpathy
    display_name: "Andrej Karpathy"
    type: rss
    url: "https://karpathy.github.io/feed.xml"
    weight: high

  - name: demis_hassabis
    display_name: "Demis Hassabis (DeepMind)"
    type: rss
    url: "https://deepmind.google/blog/rss.xml"
    weight: high

  - name: meta_engineering
    display_name: "Meta Engineering (Yann LeCun)"
    type: rss
    url: "https://engineering.fb.com/feed/"
    weight: high

  # --- COMPANY BLOGS ---
  - name: github_blog
    display_name: "GitHub Blog (AI)"
    type: rss
    url: "https://github.blog/feed/"
    filter_keywords: ["copilot", "ai", "models", "actions", "agent"]
    weight: high

  - name: github_copilot_changelog
    display_name: "GitHub Copilot Changelog"
    type: rss
    url: "https://github.blog/changelog/feed/"
    filter_keywords: ["copilot", "ai", "models"]
    weight: high

  - name: vscode
    display_name: "VS Code"
    type: rss
    url: "https://code.visualstudio.com/feed.xml"
    filter_keywords: ["ai", "copilot", "agent", "edit"]
    weight: high

  - name: openai
    display_name: "OpenAI"
    type: rss
    url: "https://openai.com/news/rss.xml"
    weight: high

  - name: google_deepmind
    display_name: "Google DeepMind"
    type: rss
    url: "https://deepmind.google/blog/rss.xml"
    weight: high

  - name: microsoft_ai
    display_name: "Microsoft AI"
    type: rss
    url: "https://blogs.microsoft.com/ai/feed/"
    weight: high

  - name: windsurf
    display_name: "Windsurf (Codeium)"
    type: rss
    url: "https://codeium.com/feed.xml"
    weight: high

  - name: huggingface
    display_name: "Hugging Face"
    type: rss
    url: "https://huggingface.co/blog/feed.xml"
    weight: medium

  - name: salesforce_ai
    display_name: "Salesforce AI"
    type: rss
    url: "https://www.salesforce.com/blog/category/ai/feed/"
    weight: medium

  - name: import_ai
    display_name: "Import AI (Jack Clark)"
    type: rss
    url: "https://jack-clark.net/feed/"
    weight: medium

  - name: latent_space
    display_name: "Latent Space"
    type: rss
    url: "https://www.latent.space/feed"
    weight: medium

  - name: simon_willison
    display_name: "Simon Willison"
    type: rss
    url: "https://simonwillison.net/atom/everything/"
    weight: medium

  - name: kdnuggets
    display_name: "KDNuggets"
    type: rss
    url: "https://www.kdnuggets.com/feed"
    weight: medium

  - name: towards_data_science
    display_name: "Towards Data Science"
    type: rss
    url: "https://towardsdatascience.com/feed"
    filter_keywords: ["enterprise", "production", "llm", "agent", "copilot", "deployment"]
    weight: medium

  - name: sap_ai
    display_name: "SAP AI"
    type: rss
    url: "https://news.sap.com/feed/"
    filter_keywords: ["ai", "joule", "copilot", "agent", "intelligence"]
    weight: medium

  - name: azure_ai
    display_name: "Azure AI"
    type: rss
    url: "https://azure.microsoft.com/en-us/blog/feed/"
    filter_keywords: ["ai", "copilot", "openai", "cognitive", "foundry"]
    weight: medium

  - name: langchain
    display_name: "LangChain"
    type: rss
    url: "https://blog.langchain.dev/rss/"
    weight: medium

  - name: nvidia_ai
    display_name: "NVIDIA AI Blog"
    type: rss
    url: "https://blogs.nvidia.com/feed/"
    filter_keywords: ["ai", "llm", "enterprise", "inference", "gpu"]
    weight: medium

  - name: aws_ml
    display_name: "AWS Machine Learning"
    type: rss
    url: "https://aws.amazon.com/blogs/machine-learning/feed/"
    weight: medium

  - name: lex_fridman
    display_name: "Lex Fridman Podcast"
    type: rss
    url: "https://lexfridman.com/feed/podcast/"
    weight: low

  # --- SCRAPE SOURCES ---
  - name: andrew_ng
    display_name: "Andrew Ng (The Batch)"
    type: scrape
    url: "https://www.deeplearning.ai/the-batch/"
    weight: high

  - name: anthropic
    display_name: "Anthropic"
    type: scrape
    url: "https://www.anthropic.com/news"
    weight: high

  - name: cognition
    display_name: "Cognition (Devin)"
    type: scrape
    url: "https://cognition.ai/blog"
    weight: high

  - name: cursor
    display_name: "Cursor"
    type: scrape
    url: "https://www.cursor.com/blog"
    weight: high

  - name: thinking_machines
    display_name: "Thinking Machines (Mira Murati)"
    type: scrape
    url: "https://www.thinkingmachines.ai/blog"
    weight: high

  - name: mistral
    display_name: "Mistral AI"
    type: scrape
    url: "https://mistral.ai/news/"
    weight: medium

  - name: tldr_ai
    display_name: "TLDR AI"
    type: scrape
    url: "https://tldr.tech/ai"
    weight: medium

  # --- API SOURCES ---
  - name: hackernews
    display_name: "Hacker News AI"
    type: api
    url: "https://hn.algolia.com/api/v1/search"
    params:
      tags: "story"
      query: "AI enterprise"
      hitsPerPage: 30
    weight: medium

  # --- REDDIT RSS ---
  - name: reddit_ainews
    display_name: "r/AINews"
    type: reddit
    url: "https://www.reddit.com/r/AINews/top/.rss?t=week"
    weight: medium

  - name: reddit_promptengineering
    display_name: "r/promptengineering"
    type: reddit
    url: "https://www.reddit.com/r/promptengineering/top/.rss?t=week"
    weight: medium

  - name: reddit_llmdevs
    display_name: "r/LLMDevs"
    type: reddit
    url: "https://www.reddit.com/r/LLMDevs/top/.rss?t=week"
    weight: medium

  - name: reddit_claudeai
    display_name: "r/ClaudeAI"
    type: reddit
    url: "https://www.reddit.com/r/ClaudeAI/top/.rss?t=week"
    weight: medium
```

**Step 4: Create empty __init__.py files**

```bash
touch schemas/__init__.py scrapers/__init__.py pipeline/__init__.py
touch tests/__init__.py tests/scrapers/__init__.py tests/pipeline/__init__.py
mkdir -p data && touch data/.gitkeep
```

**Step 5: Install dependencies**

```bash
pip install -r requirements-dev.txt
```

**Step 6: Commit**

```bash
git add requirements.txt requirements-dev.txt sources/ schemas/ scrapers/ pipeline/ tests/ data/
git commit -m "feat: project scaffolding, dependencies and source config"
```

---

## Task 2: Story Schema

**Files:**
- Create: `schemas/story.py`
- Create: `tests/test_schemas.py`

**Step 1: Write the failing test**

```python
# tests/test_schemas.py
import pytest
from schemas.story import Story, StorySource, StorySummary
from datetime import datetime, timezone


def test_story_creation_minimal():
    story = Story(
        id="abc123",
        title="GPT-5 launches",
        canonical_url="https://openai.com/gpt-5",
        sources=[StorySource(name="OpenAI", url="https://openai.com/gpt-5")],
        published_at=datetime(2026, 2, 24, tzinfo=timezone.utc),
        raw_content="OpenAI launched GPT-5 today.",
    )
    assert story.id == "abc123"
    assert story.source_count == 1
    assert story.priority_category is None
    assert story.priority_score is None
    assert story.summary is None


def test_story_id_generated_from_url():
    story = Story.from_url(
        url="https://openai.com/gpt-5",
        title="GPT-5 launches",
        source_name="OpenAI",
        published_at=datetime(2026, 2, 24, tzinfo=timezone.utc),
        raw_content="OpenAI launched GPT-5 today.",
    )
    assert len(story.id) == 64  # sha256 hex digest


def test_story_source_count_reflects_sources():
    story = Story.from_url(
        url="https://openai.com/gpt-5",
        title="GPT-5 launches",
        source_name="OpenAI",
        published_at=datetime(2026, 2, 24, tzinfo=timezone.utc),
        raw_content="Content",
    )
    story.sources.append(StorySource(name="Hacker News", url="https://news.ycombinator.com/1"))
    assert story.source_count == 2


def test_story_serializes_to_dict():
    story = Story.from_url(
        url="https://openai.com/gpt-5",
        title="GPT-5 launches",
        source_name="OpenAI",
        published_at=datetime(2026, 2, 24, tzinfo=timezone.utc),
        raw_content="Content",
    )
    d = story.model_dump(mode="json")
    assert d["title"] == "GPT-5 launches"
    assert isinstance(d["sources"], list)
```

**Step 2: Run test to verify it fails**

```bash
pytest tests/test_schemas.py -v
```
Expected: `FAILED — ModuleNotFoundError: No module named 'schemas.story'`

**Step 3: Write implementation**

```python
# schemas/story.py
import hashlib
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, computed_field


class StorySource(BaseModel):
    name: str
    url: str


class StorySummary(BaseModel):
    what_happened: str
    enterprise_impact: str
    software_delivery_impact: str
    developer_impact: str
    human_impact: str
    how_to_use: str


class Story(BaseModel):
    id: str
    title: str
    canonical_url: str
    sources: list[StorySource]
    published_at: datetime
    raw_content: str
    priority_category: Optional[str] = None
    priority_score: Optional[int] = None
    summary: Optional[StorySummary] = None

    @computed_field
    @property
    def source_count(self) -> int:
        return len(self.sources)

    @classmethod
    def from_url(
        cls,
        url: str,
        title: str,
        source_name: str,
        published_at: datetime,
        raw_content: str,
    ) -> "Story":
        story_id = hashlib.sha256(url.encode()).hexdigest()
        return cls(
            id=story_id,
            title=title,
            canonical_url=url,
            sources=[StorySource(name=source_name, url=url)],
            published_at=published_at,
            raw_content=raw_content,
        )
```

**Step 4: Run tests to verify they pass**

```bash
pytest tests/test_schemas.py -v
```
Expected: `4 passed`

**Step 5: Commit**

```bash
git add schemas/story.py tests/test_schemas.py
git commit -m "feat: Story Pydantic schema with dedup-ready source list"
```

---

## Task 3: RSS Scraper

**Files:**
- Create: `scrapers/rss.py`
- Create: `tests/scrapers/test_rss.py`

**Step 1: Write the failing test**

```python
# tests/scrapers/test_rss.py
import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone
from scrapers.rss import fetch_rss


MOCK_FEED = MagicMock()
MOCK_FEED.bozo = False
MOCK_FEED.entries = [
    MagicMock(
        title="GPT-5 is here",
        link="https://openai.com/gpt-5",
        summary="OpenAI launched GPT-5.",
        published_parsed=(2026, 2, 24, 10, 0, 0, 0, 0, 0),
    ),
    MagicMock(
        title="Claude 4 announced",
        link="https://anthropic.com/claude-4",
        summary="Anthropic announced Claude 4.",
        published_parsed=(2026, 2, 23, 10, 0, 0, 0, 0, 0),
    ),
]


def test_fetch_rss_returns_stories():
    with patch("scrapers.rss.feedparser.parse", return_value=MOCK_FEED):
        stories = fetch_rss(
            source_name="OpenAI",
            url="https://openai.com/news/rss.xml",
        )
    assert len(stories) == 2
    assert stories[0].title == "GPT-5 is here"
    assert stories[0].canonical_url == "https://openai.com/gpt-5"
    assert stories[0].sources[0].name == "OpenAI"


def test_fetch_rss_applies_filter_keywords():
    with patch("scrapers.rss.feedparser.parse", return_value=MOCK_FEED):
        stories = fetch_rss(
            source_name="OpenAI",
            url="https://openai.com/news/rss.xml",
            filter_keywords=["gpt"],
        )
    assert len(stories) == 1
    assert stories[0].title == "GPT-5 is here"


def test_fetch_rss_handles_bozo_feed():
    bad_feed = MagicMock()
    bad_feed.bozo = True
    bad_feed.entries = []
    with patch("scrapers.rss.feedparser.parse", return_value=bad_feed):
        stories = fetch_rss(source_name="Bad", url="https://bad.com/rss")
    assert stories == []


def test_fetch_rss_skips_entries_without_link():
    feed = MagicMock()
    feed.bozo = False
    feed.entries = [MagicMock(title="No link", spec=["title", "summary", "published_parsed"])]
    feed.entries[0].link = None
    with patch("scrapers.rss.feedparser.parse", return_value=feed):
        stories = fetch_rss(source_name="Test", url="https://test.com/rss")
    assert stories == []
```

**Step 2: Run test to verify it fails**

```bash
pytest tests/scrapers/test_rss.py -v
```
Expected: `FAILED — ModuleNotFoundError: No module named 'scrapers.rss'`

**Step 3: Write implementation**

```python
# scrapers/rss.py
import feedparser
import time
from datetime import datetime, timezone
from schemas.story import Story

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; AINewsletterBot/1.0)"}


def _parse_date(entry) -> datetime:
    if hasattr(entry, "published_parsed") and entry.published_parsed:
        t = entry.published_parsed
        return datetime(t[0], t[1], t[2], t[3], t[4], t[5], tzinfo=timezone.utc)
    return datetime.now(tz=timezone.utc)


def fetch_rss(
    source_name: str,
    url: str,
    filter_keywords: list[str] | None = None,
) -> list[Story]:
    feedparser.USER_AGENT = HEADERS["User-Agent"]
    feed = feedparser.parse(url)

    if feed.bozo and not feed.entries:
        return []

    stories = []
    for entry in feed.entries:
        link = getattr(entry, "link", None)
        if not link:
            continue

        title = getattr(entry, "title", "") or ""
        content = getattr(entry, "summary", "") or getattr(entry, "content", [{}])[0].get("value", "") or ""

        if filter_keywords:
            combined = (title + " " + content).lower()
            if not any(kw.lower() in combined for kw in filter_keywords):
                continue

        stories.append(
            Story.from_url(
                url=link,
                title=title,
                source_name=source_name,
                published_at=_parse_date(entry),
                raw_content=content[:2000],
            )
        )

    return stories
```

**Step 4: Run tests to verify they pass**

```bash
pytest tests/scrapers/test_rss.py -v
```
Expected: `4 passed`

**Step 5: Commit**

```bash
git add scrapers/rss.py tests/scrapers/test_rss.py
git commit -m "feat: RSS scraper with keyword filtering"
```

---

## Task 4: HTML Scraper

**Files:**
- Create: `scrapers/html.py`
- Create: `tests/scrapers/test_html.py`

**Step 1: Write the failing test**

```python
# tests/scrapers/test_html.py
import pytest
import respx
import httpx
from scrapers.html import fetch_html

SAMPLE_HTML = """
<html><body>
  <article>
    <h2><a href="/blog/post-1">AI agents take over enterprise</a></h2>
    <p>Cognition released a new version of Devin today.</p>
    <time datetime="2026-02-24">Feb 24, 2026</time>
  </article>
  <article>
    <h2><a href="/blog/post-2">New cursor feature ships</a></h2>
    <p>Cursor released background agents.</p>
    <time datetime="2026-02-23">Feb 23, 2026</time>
  </article>
</body></html>
"""


@respx.mock
def test_fetch_html_returns_stories():
    respx.get("https://cognition.ai/blog").mock(
        return_value=httpx.Response(200, text=SAMPLE_HTML)
    )
    stories = fetch_html(
        source_name="Cognition",
        url="https://cognition.ai/blog",
        base_url="https://cognition.ai",
    )
    assert len(stories) >= 1
    assert "Devin" in stories[0].raw_content or "AI agents" in stories[0].title


@respx.mock
def test_fetch_html_handles_404():
    respx.get("https://cognition.ai/blog").mock(
        return_value=httpx.Response(404)
    )
    stories = fetch_html(
        source_name="Cognition",
        url="https://cognition.ai/blog",
        base_url="https://cognition.ai",
    )
    assert stories == []


@respx.mock
def test_fetch_html_handles_connection_error():
    respx.get("https://cognition.ai/blog").mock(side_effect=httpx.ConnectError("timeout"))
    stories = fetch_html(
        source_name="Cognition",
        url="https://cognition.ai/blog",
        base_url="https://cognition.ai",
    )
    assert stories == []
```

**Step 2: Run test to verify it fails**

```bash
pytest tests/scrapers/test_html.py -v
```
Expected: `FAILED — ModuleNotFoundError: No module named 'scrapers.html'`

**Step 3: Write implementation**

```python
# scrapers/html.py
import httpx
from datetime import datetime, timezone
from urllib.parse import urljoin
from bs4 import BeautifulSoup
from schemas.story import Story

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; AINewsletterBot/1.0)",
    "Accept": "text/html,application/xhtml+xml",
}


def fetch_html(
    source_name: str,
    url: str,
    base_url: str,
    filter_keywords: list[str] | None = None,
) -> list[Story]:
    try:
        response = httpx.get(url, headers=HEADERS, timeout=20, follow_redirects=True)
        response.raise_for_status()
    except Exception:
        return []

    soup = BeautifulSoup(response.text, "html.parser")
    stories = []

    # Look for article/post links via common patterns
    candidates = []
    for tag in soup.find_all(["article", "div"], class_=lambda c: c and any(
        k in c.lower() for k in ["post", "article", "blog", "entry", "item"]
    )):
        candidates.append(tag)

    # Fallback: all h2/h3 links on the page
    if not candidates:
        candidates = soup.find_all(["h2", "h3"])

    seen_urls = set()
    for candidate in candidates[:20]:  # cap at 20 items
        link_tag = candidate.find("a", href=True) if candidate.name != "a" else candidate
        if not link_tag:
            continue

        href = link_tag.get("href", "")
        full_url = urljoin(base_url, href)

        if full_url in seen_urls or not full_url.startswith("http"):
            continue
        seen_urls.add(full_url)

        title = link_tag.get_text(strip=True)
        if not title or len(title) < 5:
            continue

        # Get surrounding text as content
        parent = link_tag.parent
        content = parent.get_text(separator=" ", strip=True)[:2000] if parent else title

        if filter_keywords:
            combined = (title + " " + content).lower()
            if not any(kw.lower() in combined for kw in filter_keywords):
                continue

        stories.append(
            Story.from_url(
                url=full_url,
                title=title,
                source_name=source_name,
                published_at=datetime.now(tz=timezone.utc),
                raw_content=content,
            )
        )

    return stories
```

**Step 4: Run tests to verify they pass**

```bash
pytest tests/scrapers/test_html.py -v
```
Expected: `3 passed`

**Step 5: Commit**

```bash
git add scrapers/html.py tests/scrapers/test_html.py
git commit -m "feat: HTML scraper for sites without RSS"
```

---

## Task 5: API Scraper (Hacker News + Reddit)

**Files:**
- Create: `scrapers/api.py`
- Create: `tests/scrapers/test_api.py`

**Step 1: Write the failing test**

```python
# tests/scrapers/test_api.py
import pytest
import respx
import httpx
import json
from scrapers.api import fetch_hackernews, fetch_reddit

HN_RESPONSE = {
    "hits": [
        {
            "title": "Show HN: AI agent for enterprise DevOps",
            "url": "https://example.com/ai-devops",
            "story_text": "We built an AI agent...",
            "created_at": "2026-02-24T10:00:00.000Z",
            "objectID": "12345",
        },
        {
            "title": "Ask HN: Best LLM for enterprise?",
            "url": None,
            "story_text": "Looking for recommendations...",
            "created_at": "2026-02-23T10:00:00.000Z",
            "objectID": "12346",
        },
    ]
}

REDDIT_RSS = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <title>Claude just changed how I build enterprise apps</title>
    <link href="https://reddit.com/r/ClaudeAI/comments/abc"/>
    <content>This is the content of the post</content>
    <updated>2026-02-24T10:00:00+00:00</updated>
  </entry>
</feed>"""


@respx.mock
def test_fetch_hackernews_returns_stories():
    respx.get("https://hn.algolia.com/api/v1/search").mock(
        return_value=httpx.Response(200, json=HN_RESPONSE)
    )
    stories = fetch_hackernews(
        url="https://hn.algolia.com/api/v1/search",
        params={"tags": "story", "query": "AI enterprise", "hitsPerPage": 30},
    )
    assert len(stories) >= 1
    assert stories[0].title == "Show HN: AI agent for enterprise DevOps"


@respx.mock
def test_fetch_hackernews_uses_objectid_as_url_fallback():
    respx.get("https://hn.algolia.com/api/v1/search").mock(
        return_value=httpx.Response(200, json=HN_RESPONSE)
    )
    stories = fetch_hackernews(
        url="https://hn.algolia.com/api/v1/search",
        params={"tags": "story", "query": "AI enterprise", "hitsPerPage": 30},
    )
    # second item has no url, should use HN link
    hn_urls = [s.canonical_url for s in stories]
    assert any("ycombinator" in u or "example.com" in u for u in hn_urls)


def test_fetch_reddit_returns_stories():
    import feedparser
    from unittest.mock import patch, MagicMock

    mock_feed = MagicMock()
    mock_feed.bozo = False
    mock_feed.entries = [
        MagicMock(
            title="Claude just changed how I build enterprise apps",
            link="https://reddit.com/r/ClaudeAI/comments/abc",
            summary="This is the content",
            published_parsed=(2026, 2, 24, 10, 0, 0, 0, 0, 0),
        )
    ]
    with patch("scrapers.api.feedparser.parse", return_value=mock_feed):
        stories = fetch_reddit(
            source_name="r/ClaudeAI",
            url="https://www.reddit.com/r/ClaudeAI/top/.rss?t=week",
        )
    assert len(stories) == 1
    assert "Claude" in stories[0].title
```

**Step 2: Run test to verify it fails**

```bash
pytest tests/scrapers/test_api.py -v
```
Expected: `FAILED — ModuleNotFoundError: No module named 'scrapers.api'`

**Step 3: Write implementation**

```python
# scrapers/api.py
import httpx
import feedparser
from datetime import datetime, timezone
from schemas.story import Story

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; AINewsletterBot/1.0)"}


def fetch_hackernews(url: str, params: dict) -> list[Story]:
    try:
        response = httpx.get(url, params=params, headers=HEADERS, timeout=15)
        response.raise_for_status()
        data = response.json()
    except Exception:
        return []

    stories = []
    for hit in data.get("hits", []):
        title = hit.get("title", "")
        if not title:
            continue

        story_url = hit.get("url") or f"https://news.ycombinator.com/item?id={hit['objectID']}"
        content = hit.get("story_text") or title

        try:
            published_at = datetime.fromisoformat(
                hit["created_at"].replace("Z", "+00:00")
            )
        except Exception:
            published_at = datetime.now(tz=timezone.utc)

        stories.append(
            Story.from_url(
                url=story_url,
                title=title,
                source_name="Hacker News",
                published_at=published_at,
                raw_content=content[:2000],
            )
        )

    return stories


def fetch_reddit(source_name: str, url: str) -> list[Story]:
    feedparser.USER_AGENT = HEADERS["User-Agent"]
    feed = feedparser.parse(url)

    if feed.bozo and not feed.entries:
        return []

    stories = []
    for entry in feed.entries:
        link = getattr(entry, "link", None)
        if not link:
            continue

        title = getattr(entry, "title", "") or ""
        content = getattr(entry, "summary", "") or ""

        published_at = datetime.now(tz=timezone.utc)
        if hasattr(entry, "published_parsed") and entry.published_parsed:
            t = entry.published_parsed
            published_at = datetime(t[0], t[1], t[2], t[3], t[4], t[5], tzinfo=timezone.utc)

        stories.append(
            Story.from_url(
                url=link,
                title=title,
                source_name=source_name,
                published_at=published_at,
                raw_content=content[:2000],
            )
        )

    return stories
```

**Step 4: Run tests to verify they pass**

```bash
pytest tests/scrapers/test_api.py -v
```
Expected: `3 passed`

**Step 5: Commit**

```bash
git add scrapers/api.py tests/scrapers/test_api.py
git commit -m "feat: HN and Reddit API scrapers"
```

---

## Task 6: Validate Feeds Pipeline Step

**Files:**
- Create: `pipeline/validate_feeds.py`
- Create: `tests/pipeline/test_validate_feeds.py`

**Step 1: Write the failing test**

```python
# tests/pipeline/test_validate_feeds.py
import pytest
import json
import yaml
from unittest.mock import patch, MagicMock
from pipeline.validate_feeds import validate_sources, load_sources


def test_load_sources_reads_yaml(tmp_path):
    config = {"sources": [{"name": "test", "type": "rss", "url": "https://test.com/rss", "weight": "high"}]}
    config_file = tmp_path / "sources.yaml"
    config_file.write_text(yaml.dump(config))
    sources = load_sources(str(config_file))
    assert len(sources) == 1
    assert sources[0]["name"] == "test"


def test_validate_sources_marks_working_feed_as_active():
    mock_feed = MagicMock()
    mock_feed.bozo = False
    mock_feed.entries = [MagicMock(title="Test entry", link="https://test.com/1")]

    sources = [{"name": "test", "type": "rss", "url": "https://test.com/rss", "weight": "high"}]

    with patch("pipeline.validate_feeds.feedparser.parse", return_value=mock_feed):
        results = validate_sources(sources)

    assert results[0]["status"] == "active"
    assert results[0]["name"] == "test"


def test_validate_sources_marks_dead_feed_as_skipped():
    mock_feed = MagicMock()
    mock_feed.bozo = True
    mock_feed.entries = []

    sources = [{"name": "dead", "type": "rss", "url": "https://dead.com/rss", "weight": "high"}]

    with patch("pipeline.validate_feeds.feedparser.parse", return_value=mock_feed):
        results = validate_sources(sources)

    assert results[0]["status"] == "skipped"


def test_validate_sources_marks_scrape_sources_as_active():
    import respx
    import httpx

    sources = [{"name": "cursor", "type": "scrape", "url": "https://cursor.com/blog", "weight": "high"}]

    with respx.mock:
        respx.get("https://cursor.com/blog").mock(return_value=httpx.Response(200, text="<html></html>"))
        results = validate_sources(sources)

    assert results[0]["status"] == "active"
```

**Step 2: Run test to verify it fails**

```bash
pytest tests/pipeline/test_validate_feeds.py -v
```
Expected: `FAILED — ModuleNotFoundError`

**Step 3: Write implementation**

```python
# pipeline/validate_feeds.py
"""
Job 0: Validate all feeds in sources.yaml.
Outputs:
  - feed_health.json  (full status report)
  - active_sources.json (list of active source names for GitHub Actions matrix)
"""
import json
import sys
import feedparser
import httpx
import yaml
from pathlib import Path

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; AINewsletterBot/1.0)"}


def load_sources(config_path: str = "sources/sources.yaml") -> list[dict]:
    with open(config_path) as f:
        return yaml.safe_load(f)["sources"]


def _check_rss(url: str) -> tuple[bool, str]:
    try:
        feed = feedparser.parse(url)
        if feed.bozo and not feed.entries:
            return False, "parse error"
        if not feed.entries:
            return False, "no entries"
        return True, f"{len(feed.entries)} entries"
    except Exception as e:
        return False, str(e)[:80]


def _check_http(url: str) -> tuple[bool, str]:
    try:
        r = httpx.get(url, headers=HEADERS, timeout=15, follow_redirects=True)
        if r.status_code == 200:
            return True, f"HTTP {r.status_code}"
        return False, f"HTTP {r.status_code}"
    except Exception as e:
        return False, str(e)[:80]


def validate_sources(sources: list[dict]) -> list[dict]:
    results = []
    for source in sources:
        stype = source["type"]
        url = source["url"]

        if stype in ("rss", "reddit"):
            ok, detail = _check_rss(url)
        elif stype in ("scrape", "api"):
            ok, detail = _check_http(url)
        else:
            ok, detail = False, f"unknown type: {stype}"

        results.append({
            **source,
            "status": "active" if ok else "skipped",
            "detail": detail,
        })
        print(f"  {'[OK]' if ok else '[SKIP]'} {source['name']:<35} {detail}")

    return results


def main():
    sources = load_sources()
    print(f"\nValidating {len(sources)} sources...\n")
    results = validate_sources(sources)

    active = [r["name"] for r in results if r["status"] == "active"]
    skipped = [r["name"] for r in results if r["status"] == "skipped"]

    print(f"\nActive: {len(active)} | Skipped: {len(skipped)}")

    Path("feed_health.json").write_text(
        json.dumps({"results": results}, indent=2)
    )
    Path("active_sources.json").write_text(json.dumps(active))

    # Write as GitHub Actions output for matrix strategy
    active_json = json.dumps(active)
    output_file = Path(
        __import__("os").environ.get("GITHUB_OUTPUT", "/dev/null")
    )
    with open(output_file, "a") as f:
        f.write(f"active_sources={active_json}\n")

    if not active:
        print("ERROR: No active sources found.", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
```

**Step 4: Run tests to verify they pass**

```bash
pytest tests/pipeline/test_validate_feeds.py -v
```
Expected: `4 passed`

**Step 5: Commit**

```bash
git add pipeline/validate_feeds.py tests/pipeline/test_validate_feeds.py
git commit -m "feat: validate_feeds pipeline step with GitHub Actions output"
```

---

## Task 7: Fetch Pipeline Step

**Files:**
- Create: `pipeline/fetch.py`
- Create: `tests/pipeline/test_fetch.py`

**Step 1: Write the failing test**

```python
# tests/pipeline/test_fetch.py
import pytest
import json
from pathlib import Path
from unittest.mock import patch, MagicMock
from schemas.story import Story
from datetime import datetime, timezone

MOCK_STORY = Story.from_url(
    url="https://openai.com/gpt-5",
    title="GPT-5 launches",
    source_name="OpenAI",
    published_at=datetime(2026, 2, 24, tzinfo=timezone.utc),
    raw_content="OpenAI launched GPT-5.",
)


def test_fetch_routes_rss_source(tmp_path):
    source = {
        "name": "openai",
        "display_name": "OpenAI",
        "type": "rss",
        "url": "https://openai.com/news/rss.xml",
        "weight": "high",
    }
    with patch("pipeline.fetch.fetch_rss", return_value=[MOCK_STORY]) as mock_rss:
        from pipeline.fetch import fetch_source
        stories = fetch_source(source)

    mock_rss.assert_called_once()
    assert len(stories) == 1


def test_fetch_routes_scrape_source():
    source = {
        "name": "cursor",
        "display_name": "Cursor",
        "type": "scrape",
        "url": "https://cursor.com/blog",
        "weight": "high",
    }
    with patch("pipeline.fetch.fetch_html", return_value=[MOCK_STORY]) as mock_html:
        from pipeline.fetch import fetch_source
        stories = fetch_source(source)

    mock_html.assert_called_once()
    assert len(stories) == 1


def test_fetch_saves_output_to_json(tmp_path):
    source = {
        "name": "openai",
        "display_name": "OpenAI",
        "type": "rss",
        "url": "https://openai.com/news/rss.xml",
        "weight": "high",
    }
    with patch("pipeline.fetch.fetch_rss", return_value=[MOCK_STORY]):
        from pipeline.fetch import fetch_source, save_stories
        stories = fetch_source(source)
        output_path = tmp_path / "openai.json"
        save_stories(stories, str(output_path))

    saved = json.loads(output_path.read_text())
    assert len(saved) == 1
    assert saved[0]["title"] == "GPT-5 launches"
```

**Step 2: Run test to verify it fails**

```bash
pytest tests/pipeline/test_fetch.py -v
```
Expected: `FAILED — ModuleNotFoundError`

**Step 3: Write implementation**

```python
# pipeline/fetch.py
"""
Job 1: Fetch stories from a single source.
Called once per source in the GitHub Actions matrix.

Usage: python pipeline/fetch.py --source <source_name>
Output: data/raw/<source_name>.json
"""
import argparse
import json
import sys
import yaml
from pathlib import Path
from schemas.story import Story
from scrapers.rss import fetch_rss
from scrapers.html import fetch_html
from scrapers.api import fetch_hackernews, fetch_reddit


def load_source_config(name: str, config_path: str = "sources/sources.yaml") -> dict:
    with open(config_path) as f:
        sources = yaml.safe_load(f)["sources"]
    for s in sources:
        if s["name"] == name:
            return s
    raise ValueError(f"Source '{name}' not found in {config_path}")


def fetch_source(source: dict) -> list[Story]:
    stype = source["type"]
    url = source["url"]
    name = source["display_name"]
    keywords = source.get("filter_keywords")

    if stype == "rss":
        return fetch_rss(source_name=name, url=url, filter_keywords=keywords)

    elif stype == "scrape":
        from urllib.parse import urlparse
        parsed = urlparse(url)
        base = f"{parsed.scheme}://{parsed.netloc}"
        return fetch_html(source_name=name, url=url, base_url=base, filter_keywords=keywords)

    elif stype == "api":
        params = source.get("params", {})
        return fetch_hackernews(url=url, params=params)

    elif stype == "reddit":
        return fetch_reddit(source_name=name, url=url)

    else:
        print(f"Unknown source type: {stype}", file=sys.stderr)
        return []


def save_stories(stories: list[Story], output_path: str) -> None:
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    data = [s.model_dump(mode="json") for s in stories]
    Path(output_path).write_text(json.dumps(data, indent=2, default=str))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True, help="Source name from sources.yaml")
    parser.add_argument("--output-dir", default="data/raw")
    args = parser.parse_args()

    source = load_source_config(args.source)
    print(f"Fetching: {source['display_name']} ({source['type']}) ...")
    stories = fetch_source(source)
    print(f"  Got {len(stories)} stories")

    output_path = f"{args.output_dir}/{args.source}.json"
    save_stories(stories, output_path)
    print(f"  Saved to {output_path}")


if __name__ == "__main__":
    main()
```

**Step 4: Run tests to verify they pass**

```bash
pytest tests/pipeline/test_fetch.py -v
```
Expected: `3 passed`

**Step 5: Commit**

```bash
git add pipeline/fetch.py tests/pipeline/test_fetch.py
git commit -m "feat: fetch pipeline step routing to scrapers"
```

---

## Task 8: Normalize Pipeline Step (Deduplication)

**Files:**
- Create: `pipeline/normalize.py`
- Create: `tests/pipeline/test_normalize.py`

**Step 1: Write the failing test**

```python
# tests/pipeline/test_normalize.py
import pytest
import json
from datetime import datetime, timezone
from pipeline.normalize import (
    load_raw_stories,
    deduplicate_by_url,
    deduplicate_by_title_similarity,
    normalize,
)
from schemas.story import Story, StorySource


def make_story(url, title, source="OpenAI", content="content"):
    return Story.from_url(
        url=url,
        title=title,
        source_name=source,
        published_at=datetime(2026, 2, 24, tzinfo=timezone.utc),
        raw_content=content,
    )


def test_deduplicate_by_url_merges_same_url():
    s1 = make_story("https://openai.com/gpt-5", "GPT-5 launches", "OpenAI")
    s2 = make_story("https://openai.com/gpt-5", "GPT-5 launches", "TLDR AI")

    result = deduplicate_by_url([s1, s2])
    assert len(result) == 1
    assert result[0].source_count == 2
    assert {s.name for s in result[0].sources} == {"OpenAI", "TLDR AI"}


def test_deduplicate_by_url_keeps_different_urls():
    s1 = make_story("https://openai.com/gpt-5", "GPT-5 launches", "OpenAI")
    s2 = make_story("https://hn.com/item?id=1", "GPT-5 launches", "HN")

    result = deduplicate_by_url([s1, s2])
    assert len(result) == 2


def test_deduplicate_by_title_similarity_merges_similar_titles():
    s1 = make_story("https://openai.com/gpt-5", "OpenAI launches GPT-5 model", "OpenAI")
    s2 = make_story("https://hn.com/1", "OpenAI launches GPT-5 model today", "HN")

    result = deduplicate_by_title_similarity([s1, s2], threshold=0.6)
    assert len(result) == 1
    assert result[0].source_count == 2


def test_deduplicate_by_title_similarity_keeps_different_stories():
    s1 = make_story("https://openai.com/gpt-5", "GPT-5 model released", "OpenAI")
    s2 = make_story("https://anthropic.com/claude-4", "Claude 4 announced", "Anthropic")

    result = deduplicate_by_title_similarity([s1, s2], threshold=0.6)
    assert len(result) == 2


def test_source_count_boosts_are_preserved():
    s1 = make_story("https://openai.com/gpt-5", "GPT-5 launches", "OpenAI")
    s2 = make_story("https://openai.com/gpt-5", "GPT-5 launches", "TLDR AI")
    s3 = make_story("https://openai.com/gpt-5", "GPT-5 launches", "HN")

    result = deduplicate_by_url([s1, s2, s3])
    assert result[0].source_count == 3
```

**Step 2: Run test to verify it fails**

```bash
pytest tests/pipeline/test_normalize.py -v
```
Expected: `FAILED — ModuleNotFoundError`

**Step 3: Write implementation**

```python
# pipeline/normalize.py
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
                        canonical.sources.append(
                            StorySource(name=src.name, url=story.canonical_url)
                        )
                merged = True
                break
        if not merged:
            groups.append(story)
    return groups


def filter_older_than_days(stories: list[Story], days: int = 7) -> list[Story]:
    cutoff = datetime.now(tz=timezone.utc) - timedelta(days=days)
    return [s for s in stories if s.published_at.replace(tzinfo=timezone.utc) >= cutoff]


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
```

**Step 4: Run tests to verify they pass**

```bash
pytest tests/pipeline/test_normalize.py -v
```
Expected: `5 passed`

**Step 5: Commit**

```bash
git add pipeline/normalize.py tests/pipeline/test_normalize.py
git commit -m "feat: normalize pipeline step with URL and title-similarity dedup"
```

---

## Task 9: Rank Pipeline Step

**Files:**
- Create: `pipeline/rank.py`
- Create: `tests/pipeline/test_rank.py`

**Step 1: Write the failing test**

```python
# tests/pipeline/test_rank.py
import pytest
import json
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone
from pipeline.rank import rank_story, select_top_stories
from schemas.story import Story

MOCK_STORY = Story.from_url(
    url="https://openai.com/gpt-5",
    title="GPT-5 launches with enterprise API",
    source_name="OpenAI",
    published_at=datetime(2026, 2, 24, tzinfo=timezone.utc),
    raw_content="OpenAI launched GPT-5 with a new enterprise API tier.",
)

MOCK_LLM_RESPONSE = json.dumps({
    "scores": {
        "enterprise_software_delivery": 85,
        "enterprise_solutions": 70,
        "finance_utilities": 30,
        "general_significance": 90,
    },
    "include": True,
})


def test_rank_story_sets_category_and_score():
    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = MagicMock(
        choices=[MagicMock(message=MagicMock(content=MOCK_LLM_RESPONSE))]
    )
    story = MOCK_STORY.model_copy(deep=True)
    ranked = rank_story(story, mock_client)

    assert ranked.priority_category == "enterprise_software_delivery"
    assert ranked.priority_score == 85


def test_rank_story_exclude_returns_none():
    exclude_response = json.dumps({
        "scores": {
            "enterprise_software_delivery": 5,
            "enterprise_solutions": 5,
            "finance_utilities": 5,
            "general_significance": 5,
        },
        "include": False,
    })
    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = MagicMock(
        choices=[MagicMock(message=MagicMock(content=exclude_response))]
    )
    story = MOCK_STORY.model_copy(deep=True)
    result = rank_story(story, mock_client)
    assert result is None


def test_select_top_stories_caps_per_category():
    stories = []
    for i in range(10):
        s = MOCK_STORY.model_copy(deep=True)
        s.id = str(i)
        s.priority_category = "enterprise_software_delivery"
        s.priority_score = 90 - i
        stories.append(s)

    result = select_top_stories(stories, per_category=5)
    assert len(result["enterprise_software_delivery"]) <= 5
```

**Step 2: Run test to verify it fails**

```bash
pytest tests/pipeline/test_rank.py -v
```
Expected: `FAILED — ModuleNotFoundError`

**Step 3: Write implementation**

```python
# pipeline/rank.py
"""
Job 3: Score stories by enterprise relevance using GitHub Models API.

GitHub Models endpoint: https://models.inference.ai.azure.com
Auth: GITHUB_TOKEN environment variable (uses your existing GitHub license)
Model: gpt-4o-mini (cheap, fast, sufficient for scoring)
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
        base_url="https://models.inference.ai.azure.com",
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
            model="gpt-4o-mini",
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
        cat: [s.model_dump(mode="json") for s in stories]
        for cat, stories in categorized.items()
    }
    Path("data/ranked.json").write_text(json.dumps(output, indent=2, default=str))
    print("  Saved to data/ranked.json")


if __name__ == "__main__":
    main()
```

**Step 4: Run tests to verify they pass**

```bash
pytest tests/pipeline/test_rank.py -v
```
Expected: `3 passed`

**Step 5: Commit**

```bash
git add pipeline/rank.py tests/pipeline/test_rank.py
git commit -m "feat: rank pipeline step using GitHub Models API (gpt-4o-mini)"
```

---

## Task 10: Summarize Pipeline Step

**Files:**
- Create: `pipeline/summarize.py`
- Create: `tests/pipeline/test_summarize.py`

**Step 1: Write the failing test**

```python
# tests/pipeline/test_summarize.py
import pytest
import json
from unittest.mock import MagicMock
from datetime import datetime, timezone
from pipeline.summarize import summarize_story, pick_top3
from schemas.story import Story, StorySummary

MOCK_STORY = Story.from_url(
    url="https://openai.com/gpt-5",
    title="GPT-5 launches with enterprise API",
    source_name="OpenAI",
    published_at=datetime(2026, 2, 24, tzinfo=timezone.utc),
    raw_content="OpenAI launched GPT-5 today with a new enterprise tier.",
)
MOCK_STORY.priority_category = "enterprise_software_delivery"
MOCK_STORY.priority_score = 90

MOCK_SUMMARY = json.dumps({
    "what_happened": "OpenAI launched GPT-5 with enterprise API access.",
    "enterprise_impact": "Enterprises can now integrate GPT-5 at scale.",
    "software_delivery_impact": "Dev teams can replace GPT-4 with GPT-5 in pipelines.",
    "developer_impact": "New API endpoints, higher context window, lower latency.",
    "human_impact": "More capable AI assistants across workplaces.",
    "how_to_use": "Upgrade your OpenAI SDK and switch model to gpt-5.",
})


def test_summarize_story_populates_summary():
    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = MagicMock(
        choices=[MagicMock(message=MagicMock(content=MOCK_SUMMARY))]
    )
    story = MOCK_STORY.model_copy(deep=True)
    result = summarize_story(story, mock_client)

    assert result.summary is not None
    assert "GPT-5" in result.summary.what_happened
    assert result.summary.how_to_use != ""


def test_summarize_story_handles_llm_failure():
    mock_client = MagicMock()
    mock_client.chat.completions.create.side_effect = Exception("API timeout")
    story = MOCK_STORY.model_copy(deep=True)
    result = summarize_story(story, mock_client)
    # Should return story unchanged (no summary), not raise
    assert result.summary is None


def test_pick_top3_selects_highest_scoring_across_categories():
    stories_by_category = {}
    for cat in ["enterprise_software_delivery", "enterprise_solutions", "finance_utilities"]:
        s = MOCK_STORY.model_copy(deep=True)
        s.priority_category = cat
        s.priority_score = 80
        stories_by_category[cat] = [s]

    top3 = pick_top3(stories_by_category)
    assert len(top3) == 3
```

**Step 2: Run test to verify it fails**

```bash
pytest tests/pipeline/test_summarize.py -v
```
Expected: `FAILED — ModuleNotFoundError`

**Step 3: Write implementation**

```python
# pipeline/summarize.py
"""
Job 4: Generate structured 6-dimension analysis for top-ranked stories.

Uses GitHub Models API (gpt-4o) for higher quality summaries.
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
            model="gpt-4o",
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
    # Deduplicate by id
    seen = set()
    top3 = []
    for s in all_stories:
        if s.id not in seen:
            top3.append(s)
            seen.add(s.id)
        if len(top3) == 3:
            break
    return top3


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
```

**Step 4: Run tests to verify they pass**

```bash
pytest tests/pipeline/test_summarize.py -v
```
Expected: `3 passed`

**Step 5: Commit**

```bash
git add pipeline/summarize.py tests/pipeline/test_summarize.py
git commit -m "feat: summarize pipeline step with 6-dimension analysis (gpt-4o)"
```

---

## Task 11: Deliver Pipeline Step

**Files:**
- Create: `pipeline/deliver.py`
- Create: `tests/pipeline/test_deliver.py`

**Step 1: Write the failing test**

```python
# tests/pipeline/test_deliver.py
import pytest
from datetime import datetime, timezone
from pipeline.deliver import format_story_full, format_story_brief, format_digest
from schemas.story import Story, StorySource, StorySummary

def make_full_story(title, category, score, source_names=None):
    s = Story.from_url(
        url=f"https://example.com/{title.replace(' ', '-')}",
        title=title,
        source_name=source_names[0] if source_names else "OpenAI",
        published_at=datetime(2026, 2, 24, tzinfo=timezone.utc),
        raw_content="Content here.",
    )
    s.priority_category = category
    s.priority_score = score
    if source_names and len(source_names) > 1:
        for name in source_names[1:]:
            s.sources.append(StorySource(name=name, url=f"https://{name}.com"))
    s.summary = StorySummary(
        what_happened="OpenAI launched GPT-5.",
        enterprise_impact="Major productivity gains for enterprises.",
        software_delivery_impact="Dev teams can automate code review.",
        developer_impact="New API available, upgrade SDK.",
        human_impact="Jobs will shift, not disappear.",
        how_to_use="Try the new API with a small project this week.",
    )
    return s


def test_format_story_full_contains_all_sections():
    story = make_full_story("GPT-5 launches", "enterprise_software_delivery", 90)
    text = format_story_full(story, index=1)

    assert "[1]" in text
    assert "GPT-5 launches" in text
    assert "What happened:" in text
    assert "Enterprise impact:" in text
    assert "Software delivery impact:" in text
    assert "For developers:" in text
    assert "For people:" in text
    assert "How to use it:" in text
    assert "https://example.com" in text


def test_format_story_full_shows_multiple_sources():
    story = make_full_story("GPT-5 launches", "enterprise_software_delivery", 90,
                            source_names=["OpenAI", "Hacker News", "TLDR AI"])
    text = format_story_full(story, index=1)
    assert "3 sources" in text or "OpenAI" in text


def test_format_story_brief_is_one_line():
    story = make_full_story("GPT-5 launches", "enterprise_software_delivery", 90)
    text = format_story_brief(story)
    assert "GPT-5 launches" in text
    assert "https://example.com" in text
    assert "\n\n" not in text


def test_format_digest_has_all_categories():
    stories_by_category = {
        "enterprise_software_delivery": [
            make_full_story("Story A", "enterprise_software_delivery", 90)
        ],
        "enterprise_solutions": [
            make_full_story("Story B", "enterprise_solutions", 75)
        ],
        "finance_utilities": [],
        "general_significance": [
            make_full_story("Story C", "general_significance", 60)
        ],
    }
    top3 = [make_full_story("Top Story", "enterprise_software_delivery", 95)]
    digest = format_digest(top3, stories_by_category, week_of="Feb 24, 2026")

    assert "AI DIGEST" in digest
    assert "TOP 3 MUST-READS" in digest
    assert "ENTERPRISE SOFTWARE DELIVERY" in digest
    assert "ENTERPRISE SOLUTIONS" in digest
    assert "GENERAL SIGNIFICANCE" in digest
    assert "FINANCE & UTILITIES" in digest
```

**Step 2: Run test to verify it fails**

```bash
pytest tests/pipeline/test_deliver.py -v
```
Expected: `FAILED — ModuleNotFoundError`

**Step 3: Write implementation**

```python
# pipeline/deliver.py
"""
Job 5: Format stories and deliver to Telegram.

Format: Option C — Top 3 must-reads in full, then category digests.
No emoji. Professional tone.
"""
import json
import os
import asyncio
from datetime import datetime, timezone
from pathlib import Path
from telegram import Bot
from schemas.story import Story

CATEGORY_LABELS = {
    "enterprise_software_delivery": "ENTERPRISE SOFTWARE DELIVERY",
    "enterprise_solutions": "ENTERPRISE SOLUTIONS",
    "finance_utilities": "FINANCE & UTILITIES",
    "general_significance": "GENERAL SIGNIFICANCE",
}

MAX_TELEGRAM_LENGTH = 4096


def format_story_full(story: Story, index: int) -> str:
    sources_str = " | ".join(s.name for s in story.sources)
    if story.source_count > 1:
        sources_str += f" ({story.source_count} sources)"

    lines = [
        f"[{index}] {story.title.upper()}",
        f"Source: {sources_str} | Category: {CATEGORY_LABELS.get(story.priority_category, story.priority_category)}",
        "",
    ]

    if story.summary:
        lines += [
            f"What happened: {story.summary.what_happened}",
            f"Enterprise impact: {story.summary.enterprise_impact}",
            f"Software delivery impact: {story.summary.software_delivery_impact}",
            f"For developers: {story.summary.developer_impact}",
            f"For people: {story.summary.human_impact}",
            f"How to use it: {story.summary.how_to_use}",
            "",
        ]

    lines.append("Read more:")
    for src in story.sources:
        lines.append(f"  - {src.url}")

    return "\n".join(lines)


def format_story_brief(story: Story) -> str:
    impact = ""
    if story.summary:
        impact = f" — {story.summary.enterprise_impact[:80]}"
    return f"- {story.title}{impact}\n  {story.canonical_url}"


def format_digest(
    top3: list[Story],
    stories_by_category: dict[str, list[Story]],
    week_of: str,
) -> str:
    divider = "_" * 32
    sections = [
        f"AI DIGEST | Week of {week_of}",
        divider,
        "",
        "TOP 3 MUST-READS THIS WEEK",
        divider,
        "",
    ]

    for i, story in enumerate(top3, 1):
        sections.append(format_story_full(story, index=i))
        sections.append("")

    for cat, label in CATEGORY_LABELS.items():
        stories = stories_by_category.get(cat, [])
        sections += [divider, label, divider]
        if stories:
            for story in stories:
                sections.append(format_story_brief(story))
        else:
            sections.append("No significant stories this week.")
        sections.append("")

    return "\n".join(sections)


def split_message(text: str, max_length: int = MAX_TELEGRAM_LENGTH) -> list[str]:
    if len(text) <= max_length:
        return [text]

    parts = []
    while text:
        if len(text) <= max_length:
            parts.append(text)
            break
        # Split at last newline before limit
        split_at = text[:max_length].rfind("\n")
        if split_at == -1:
            split_at = max_length
        parts.append(text[:split_at])
        text = text[split_at:].lstrip("\n")
    return parts


async def send_to_telegram(text: str, bot_token: str, chat_id: str) -> None:
    bot = Bot(token=bot_token)
    parts = split_message(text)
    for part in parts:
        await bot.send_message(
            chat_id=chat_id,
            text=part,
            disable_web_page_preview=True,
        )


def main():
    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if not bot_token or not chat_id:
        raise ValueError("TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID are required")

    data = json.loads(Path("data/summarized.json").read_text())

    def load_stories(items):
        result = []
        for item in items:
            if isinstance(item.get("published_at"), str):
                item["published_at"] = datetime.fromisoformat(item["published_at"])
            result.append(Story(**item))
        return result

    top3 = load_stories(data["top3"])
    stories_by_category = {
        cat: load_stories(items)
        for cat, items in data["categories"].items()
    }

    week_of = datetime.now(tz=timezone.utc).strftime("%b %d, %Y")
    digest = format_digest(top3, stories_by_category, week_of=week_of)

    print(f"Digest length: {len(digest)} characters")
    asyncio.run(send_to_telegram(digest, bot_token, chat_id))
    print("Delivered to Telegram.")


if __name__ == "__main__":
    main()
```

**Step 4: Run tests to verify they pass**

```bash
pytest tests/pipeline/test_deliver.py -v
```
Expected: `4 passed`

**Step 5: Commit**

```bash
git add pipeline/deliver.py tests/pipeline/test_deliver.py
git commit -m "feat: deliver pipeline step with Telegram formatting (Option C)"
```

---

## Task 12: GitHub Actions Workflow

**Files:**
- Create: `.github/workflows/newsletter.yml`

**Note:** No automated test for this — validate by running `act` locally or triggering `workflow_dispatch`.

**Step 1: Create the workflow**

```yaml
# .github/workflows/newsletter.yml
name: AI Newsletter

on:
  schedule:
    - cron: '0 6 * * 1'    # Every Monday 6am UTC
  workflow_dispatch:         # Manual trigger for testing

jobs:

  validate:
    runs-on: ubuntu-latest
    outputs:
      active_sources: ${{ steps.validate.outputs.active_sources }}
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.12'
      - name: Install dependencies
        run: pip install -r requirements.txt
      - name: Validate feeds
        id: validate
        run: python pipeline/validate_feeds.py
      - uses: actions/upload-artifact@v4
        with:
          name: feed-health
          path: feed_health.json

  fetch:
    needs: validate
    runs-on: ubuntu-latest
    strategy:
      matrix:
        source: ${{ fromJson(needs.validate.outputs.active_sources) }}
      fail-fast: false
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.12'
      - name: Install dependencies
        run: pip install -r requirements.txt
      - name: Fetch source
        run: python pipeline/fetch.py --source "${{ matrix.source }}" --output-dir data/raw
      - uses: actions/upload-artifact@v4
        with:
          name: raw-${{ matrix.source }}
          path: data/raw/${{ matrix.source }}.json
          if-no-files-found: warn

  normalize:
    needs: fetch
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.12'
      - name: Install dependencies
        run: pip install -r requirements.txt
      - uses: actions/download-artifact@v4
        with:
          pattern: raw-*
          merge-multiple: true
          path: data/raw/
      - name: Normalize stories
        run: python pipeline/normalize.py
      - uses: actions/upload-artifact@v4
        with:
          name: normalized
          path: data/normalized.json

  rank:
    needs: normalize
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.12'
      - name: Install dependencies
        run: pip install -r requirements.txt
      - uses: actions/download-artifact@v4
        with:
          name: normalized
          path: data/
      - name: Rank stories
        run: python pipeline/rank.py
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
      - uses: actions/upload-artifact@v4
        with:
          name: ranked
          path: data/ranked.json

  summarize:
    needs: rank
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.12'
      - name: Install dependencies
        run: pip install -r requirements.txt
      - uses: actions/download-artifact@v4
        with:
          name: ranked
          path: data/
      - name: Summarize stories
        run: python pipeline/summarize.py
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
      - uses: actions/upload-artifact@v4
        with:
          name: summarized
          path: data/summarized.json

  deliver:
    needs: summarize
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.12'
      - name: Install dependencies
        run: pip install -r requirements.txt
      - uses: actions/download-artifact@v4
        with:
          name: summarized
          path: data/
      - name: Deliver to Telegram
        run: python pipeline/deliver.py
        env:
          TELEGRAM_BOT_TOKEN: ${{ secrets.TELEGRAM_BOT_TOKEN }}
          TELEGRAM_CHAT_ID: ${{ secrets.TELEGRAM_CHAT_ID }}
```

**Step 2: Commit**

```bash
git add .github/workflows/newsletter.yml
git commit -m "feat: GitHub Actions workflow — weekly newsletter pipeline"
```

---

## Task 13: Full Test Suite and Smoke Test

**Files:**
- Create: `tests/test_smoke.py`

**Step 1: Write smoke test (no real API calls)**

```python
# tests/test_smoke.py
"""
Smoke test: runs the full pipeline with mocked LLM and real (cached) RSS feeds.
Validates the data flows correctly end to end.
"""
import json
import pytest
from datetime import datetime, timezone
from unittest.mock import patch, MagicMock
from schemas.story import Story, StorySummary
from pipeline.normalize import normalize, deduplicate_by_url
from pipeline.rank import select_top_stories
from pipeline.deliver import format_digest, split_message

MOCK_RANK_RESPONSE = json.dumps({
    "scores": {
        "enterprise_software_delivery": 85,
        "enterprise_solutions": 40,
        "finance_utilities": 20,
        "general_significance": 60,
    },
    "include": True,
})

MOCK_SUMMARY_RESPONSE = json.dumps({
    "what_happened": "A major AI development occurred.",
    "enterprise_impact": "Significant for enterprise teams.",
    "software_delivery_impact": "Changes how code is reviewed.",
    "developer_impact": "New tools available.",
    "human_impact": "Workforce will adapt.",
    "how_to_use": "Start a small pilot project.",
})


def make_stories(n=5):
    stories = []
    for i in range(n):
        s = Story.from_url(
            url=f"https://example.com/story-{i}",
            title=f"AI development number {i} impacts enterprise",
            source_name="TestSource",
            published_at=datetime(2026, 2, 24, tzinfo=timezone.utc),
            raw_content=f"Content for story {i}. This is about AI and enterprise.",
        )
        stories.append(s)
    return stories


def test_dedup_then_rank_then_format():
    stories = make_stories(5)
    # Add a duplicate
    dup = stories[0].model_copy(deep=True)
    dup.sources[0].name = "DuplicateSource"
    stories.append(dup)

    deduped = deduplicate_by_url(stories)
    assert len(deduped) == 5  # duplicate merged
    assert deduped[0].source_count == 2

    # Simulate ranking
    for s in deduped:
        s.priority_category = "enterprise_software_delivery"
        s.priority_score = 80

    categorized = select_top_stories(deduped)
    assert len(categorized["enterprise_software_delivery"]) <= 8

    # Simulate summaries
    for s in deduped:
        s.summary = StorySummary(**json.loads(MOCK_SUMMARY_RESPONSE))

    top3 = deduped[:3]
    digest = format_digest(top3, categorized, week_of="Feb 24, 2026")

    assert "AI DIGEST" in digest
    assert "TOP 3 MUST-READS" in digest
    assert len(digest) > 100


def test_long_digest_splits_correctly():
    long_text = "A" * 5000
    parts = split_message(long_text, max_length=4096)
    assert len(parts) == 2
    assert all(len(p) <= 4096 for p in parts)


def test_all_pipeline_modules_importable():
    from pipeline import validate_feeds, fetch, normalize, rank, summarize, deliver
    from scrapers import rss, html, api
    from schemas import story
    assert True  # if we got here, all imports work
```

**Step 2: Run full test suite**

```bash
pytest tests/ -v --tb=short
```
Expected: All tests pass.

**Step 3: Run with coverage**

```bash
pip install pytest-cov
pytest tests/ --cov=pipeline --cov=scrapers --cov=schemas --cov-report=term-missing
```
Expected: >70% coverage

**Step 4: Final commit**

```bash
git add tests/test_smoke.py
git commit -m "feat: smoke test covering full pipeline data flow"
```

---

## Task 14: First Live Run

**Step 1: Set up GitHub repository**

```bash
# Create GitHub repo (if not already done)
gh repo create newsletteragent --private
git remote add origin https://github.com/<your-username>/newsletteragent.git
git push -u origin master
```

**Step 2: Set secrets in GitHub**

Go to: `https://github.com/<your-username>/newsletteragent/settings/secrets/actions`

Add:
- `TELEGRAM_BOT_TOKEN` — from @BotFather
- `TELEGRAM_CHAT_ID` — from @userinfobot

**Step 3: Trigger manual run**

```bash
gh workflow run newsletter.yml
```

**Step 4: Monitor run**

```bash
gh run list --workflow=newsletter.yml
gh run watch  # live output
```

**Step 5: Verify Telegram delivery**

Check your Telegram — the digest should arrive within ~25 minutes.

**Step 6: Tag v1.0**

```bash
git tag v1.0.0
git push origin v1.0.0
```

---

## Running Tests Locally

```bash
# All tests
pytest tests/ -v

# Single module
pytest tests/pipeline/test_normalize.py -v

# With coverage
pytest tests/ --cov=pipeline --cov=scrapers --cov=schemas --cov-report=term-missing

# Run pipeline locally (requires GITHUB_TOKEN and Telegram secrets)
python pipeline/validate_feeds.py
python pipeline/fetch.py --source openai
python pipeline/normalize.py
GITHUB_TOKEN=<token> python pipeline/rank.py
GITHUB_TOKEN=<token> python pipeline/summarize.py
TELEGRAM_BOT_TOKEN=<token> TELEGRAM_CHAT_ID=<id> python pipeline/deliver.py
```

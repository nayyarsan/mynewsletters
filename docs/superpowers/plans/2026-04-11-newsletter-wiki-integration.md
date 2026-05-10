# Newsletter Wiki Integration — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add wiki output to the newsletteragent pipeline and centralise LLM backend selection so the full pipeline runs locally with Gemma3 (LLM_BACKEND=local) or in CI with GitHub Models (LLM_BACKEND=github, default).

**Architecture:** A new `pipeline/llm_config.py` module exposes `get_client(step) -> (OpenAI, model_name)` and is imported by rank, summarize, and wiki steps. `pipeline/wiki.py` reads `data/summarized.json` and writes story articles, topic articles, a weekly digest, and an index to `D:/myprojects/wiki/`. `pipeline/run.py` chains all steps locally and pings Ollama if LLM_BACKEND=local.

**Tech Stack:** Python 3.11+, openai SDK, httpx, pydantic, pytest, monkeypatch

---

## File Map

| Action | Path | Responsibility |
|--------|------|----------------|
| Create | `pipeline/llm_config.py` | Central LLM config — `get_client(step)` returns `(OpenAI, model_name)` |
| Create | `pipeline/wiki.py` | Wiki build step — reads `summarized.json`, writes to `D:/myprojects/wiki/` |
| Create | `pipeline/run.py` | Local full-pipeline runner — chains all steps |
| Create | `tests/pipeline/test_llm_config.py` | Unit tests for llm_config |
| Create | `tests/pipeline/test_wiki.py` | Unit tests for wiki step |
| Create | `tests/pipeline/test_run.py` | Unit test for run.py Ollama ping |
| Modify | `pipeline/rank.py` | Remove local `get_client()`, add `model` param to rank/classify functions, use llm_config in main() |
| Modify | `pipeline/summarize.py` | Remove `get_client` import from rank, add `model` param to `summarize_story`, use llm_config in main() |
| Modify | `tests/pipeline/test_rank.py` | Update monkeypatch target from `mod.get_client` to `pipeline.llm_config.get_client` |
| Modify | `tests/pipeline/test_summarize.py` | Same update + update `fake_summarize` signature |

---

## Task 1: pipeline/llm_config.py

**Files:**
- Create: `pipeline/llm_config.py`
- Create: `tests/pipeline/test_llm_config.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/pipeline/test_llm_config.py
import importlib
import sys
import pytest
from unittest.mock import patch


def _load(monkeypatch, backend=None):
    """Delete cached module and re-import with the given env var."""
    if backend is not None:
        monkeypatch.setenv("LLM_BACKEND", backend)
    else:
        monkeypatch.delenv("LLM_BACKEND", raising=False)
    monkeypatch.delitem(sys.modules, "pipeline.llm_config", raising=False)
    return importlib.import_module("pipeline.llm_config")


def test_github_backend_is_default(monkeypatch):
    mod = _load(monkeypatch)
    assert mod.LLM_BACKEND == "github"
    client, model = mod.get_client("rank")
    assert model == "openai/gpt-4o-mini"
    assert "github" in str(client.base_url)


def test_local_backend(monkeypatch):
    mod = _load(monkeypatch, "local")
    assert mod.LLM_BACKEND == "local"
    client, model = mod.get_client("rank")
    assert model == "gemma3"
    assert "11434" in str(client.base_url)


def test_unknown_backend_raises(monkeypatch):
    monkeypatch.setenv("LLM_BACKEND", "bogus")
    monkeypatch.delitem(sys.modules, "pipeline.llm_config", raising=False)
    with pytest.raises(ValueError, match="Unknown LLM_BACKEND"):
        importlib.import_module("pipeline.llm_config")
```

- [ ] **Step 2: Run tests to verify they fail**

```
cd D:/myprojects/newsletteragent
pytest tests/pipeline/test_llm_config.py -v
```

Expected: `ModuleNotFoundError: No module named 'pipeline.llm_config'`

- [ ] **Step 3: Create pipeline/llm_config.py**

```python
# pipeline/llm_config.py
import os
from openai import OpenAI

LLM_BACKEND = os.environ.get("LLM_BACKEND", "github")

BACKENDS = {
    "github": {
        "base_url": "https://models.github.ai/inference",
        "api_key": os.environ.get("GITHUB_TOKEN", ""),
        "models": {
            "rank":      "openai/gpt-4o-mini",
            "summarize": "openai/gpt-4o",
            "wiki":      "openai/gpt-4o-mini",
        },
    },
    "local": {
        "base_url": "http://localhost:11434/v1",
        "api_key": "ollama",
        "models": {
            "rank":      "gemma3",
            "summarize": "gemma3",
            "wiki":      "gemma3",
        },
    },
}

if LLM_BACKEND not in BACKENDS:
    raise ValueError(
        f"Unknown LLM_BACKEND '{LLM_BACKEND}'. Must be one of: {list(BACKENDS)}"
    )


def get_client(step: str) -> tuple[OpenAI, str]:
    """Return (OpenAI client, model name) for the given pipeline step."""
    backend = BACKENDS[LLM_BACKEND]
    client = OpenAI(base_url=backend["base_url"], api_key=backend["api_key"])
    return client, backend["models"][step]
```

- [ ] **Step 4: Run tests to verify they pass**

```
pytest tests/pipeline/test_llm_config.py -v
```

Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add pipeline/llm_config.py tests/pipeline/test_llm_config.py
git commit -m "feat: add pipeline/llm_config.py with LLM_BACKEND switching"
```

---

## Task 2: Refactor pipeline/rank.py

**Files:**
- Modify: `pipeline/rank.py`
- Modify: `tests/pipeline/test_rank.py`

The change: remove the local `get_client()` function, add `model` parameter to `rank_story()`, `rank_batch()`, and `classify_sdlc_tags()`, and update `main()` to get (client, model) from `llm_config`.

- [ ] **Step 1: Verify current tests pass before touching anything**

```
pytest tests/pipeline/test_rank.py -v
```

Expected: all passing. Note the count — you must not regress any test.

- [ ] **Step 2: Add model parameter to rank_story, rank_batch, classify_sdlc_tags**

In `pipeline/rank.py`:

**Remove** the entire `get_client()` function (lines 157–164 — the function that creates the OpenAI client with the GITHUB_TOKEN).

**Change `rank_story` signature** from:
```python
def rank_story(story: Story, client: OpenAI) -> Story | None:
```
to:
```python
def rank_story(story: Story, client: OpenAI, model: str = "openai/gpt-4o-mini") -> Story | None:
```
Replace the hardcoded `model="openai/gpt-4o-mini"` inside it with the `model` variable:
```python
response = client.chat.completions.create(
    model=model,
    ...
)
```

**Change `rank_batch` signature** from:
```python
def rank_batch(batch: list[Story], client: OpenAI, retries: int = 2) -> list[Story]:
```
to:
```python
def rank_batch(batch: list[Story], client: OpenAI, model: str = "openai/gpt-4o-mini", retries: int = 2) -> list[Story]:
```
Replace both hardcoded `model="openai/gpt-4o-mini"` inside it with the `model` variable.

**Change `classify_sdlc_tags` signature** from:
```python
def classify_sdlc_tags(stories: list[Story], client: OpenAI) -> list[Story]:
```
to:
```python
def classify_sdlc_tags(stories: list[Story], client: OpenAI, model: str = "openai/gpt-4o-mini") -> list[Story]:
```
Replace hardcoded `model="openai/gpt-4o-mini"` inside it with the `model` variable.

**Update `main()`** — replace:
```python
def main():
    client = get_client()
    source_weights = _load_source_weights()
    ...
    results = rank_batch(batch, client)
    ...
    ranked = classify_sdlc_tags(ranked, client)
```
with:
```python
def main():
    from pipeline import llm_config
    client, model = llm_config.get_client("rank")
    source_weights = _load_source_weights()
    ...
    results = rank_batch(batch, client, model)
    ...
    ranked = classify_sdlc_tags(ranked, client, model)
```

Also pass `model` to the `rank_story` call if present anywhere in main (there isn't one in main — rank_story is only in unit tests and backwards-compat path).

- [ ] **Step 3: Run rank tests to verify nothing regressed**

```
pytest tests/pipeline/test_rank.py -v
```

Expected: same count passing as Step 1. The existing tests don't pass `model` so they use the default.

- [ ] **Step 4: Update the one test that mocks get_client**

In `tests/pipeline/test_rank.py`, find `test_14_day_cutoff_in_main`. It currently has:
```python
monkeypatch.setattr(mod, "get_client", lambda: None)
```

Replace those two lines with:
```python
import pipeline.llm_config
monkeypatch.setattr(pipeline.llm_config, "get_client", lambda step: (None, "openai/gpt-4o-mini"))
```

Also remove `get_client` from the import at the top of that test file if it's there (it isn't — check line 4: imports are from `pipeline.rank` but not `get_client`).

- [ ] **Step 5: Run tests again**

```
pytest tests/pipeline/test_rank.py -v
```

Expected: all passing.

- [ ] **Step 6: Commit**

```bash
git add pipeline/rank.py tests/pipeline/test_rank.py
git commit -m "refactor: rank.py uses llm_config.get_client, adds model param"
```

---

## Task 3: Refactor pipeline/summarize.py

**Files:**
- Modify: `pipeline/summarize.py`
- Modify: `tests/pipeline/test_summarize.py`

Current state: `summarize.py` imports `get_client` from `pipeline.rank` and uses `model="openai/gpt-4o"` hardcoded in `summarize_story()`.

- [ ] **Step 1: Verify current tests pass**

```
pytest tests/pipeline/test_summarize.py -v
```

Note the passing count.

- [ ] **Step 2: Update summarize.py imports and add model parameter**

In `pipeline/summarize.py`:

**Change line 13** from:
```python
from pipeline.rank import get_client, recency_multiplier
```
to:
```python
from pipeline.rank import recency_multiplier
from pipeline import llm_config
```

**Change `summarize_story` signature** from:
```python
def summarize_story(story: Story, client: OpenAI, cache: dict | None = None) -> Story:
```
to:
```python
def summarize_story(story: Story, client: OpenAI, model: str = "openai/gpt-4o", cache: dict | None = None) -> Story:
```

Inside `summarize_story`, replace:
```python
response = client.chat.completions.create(
    model="openai/gpt-4o",  # best available on GitHub Models API
```
with:
```python
response = client.chat.completions.create(
    model=model,
```

**Update `main()`** — replace:
```python
def main():
    client = get_client()
```
with:
```python
def main():
    client, model = llm_config.get_client("summarize")
```

Then update the `summarize_story` calls in main. Current:
```python
top3 = [summarize_story(s, client, cache) for s in top3]
```
Change to:
```python
top3 = [summarize_story(s, client, model, cache) for s in top3]
```

- [ ] **Step 3: Run tests to check for regressions**

```
pytest tests/pipeline/test_summarize.py -v
```

Expected: most tests pass. `test_main_summarises_only_top3` may fail because it still patches `mod.get_client`.

- [ ] **Step 4: Update test_main_summarises_only_top3**

In `tests/pipeline/test_summarize.py`, in `test_main_summarises_only_top3`:

Replace:
```python
monkeypatch.setattr(mod, "get_client", lambda: None)
```
with:
```python
import pipeline.llm_config
monkeypatch.setattr(pipeline.llm_config, "get_client", lambda step: (None, "openai/gpt-4o"))
```

Also update `fake_summarize` signature from:
```python
def fake_summarize(story, client, cache=None):
```
to:
```python
def fake_summarize(story, client, model="openai/gpt-4o", cache=None):
```

- [ ] **Step 5: Run all tests**

```
pytest tests/pipeline/test_summarize.py -v
```

Expected: all passing (same count as Step 1).

- [ ] **Step 6: Run the full test suite to check cross-module**

```
pytest tests/ -v --tb=short
```

Expected: no new failures introduced by the refactor.

- [ ] **Step 7: Commit**

```bash
git add pipeline/summarize.py tests/pipeline/test_summarize.py
git commit -m "refactor: summarize.py uses llm_config.get_client, adds model param"
```

---

## Task 4: pipeline/wiki.py — pure-Python functions

This task creates `pipeline/wiki.py` with the helpers and story-article/index functions. No LLM calls yet.

**Files:**
- Create: `pipeline/wiki.py` (partial — helpers + story + index)
- Create: `tests/pipeline/test_wiki.py` (partial — story + index tests)

- [ ] **Step 1: Write the failing tests (story articles + index)**

```python
# tests/pipeline/test_wiki.py
import pytest
from datetime import date, datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch
from schemas.story import Story, StorySummary
from pipeline.wiki import write_story_articles, write_index


def _make_story(title="GPT-5 Launches", sdlc_tags=None, has_summary=True):
    story = Story.from_url(
        url="https://example.com/gpt-5",
        title=title,
        source_name="OpenAI",
        published_at=datetime(2026, 4, 11, tzinfo=timezone.utc),
        raw_content="OpenAI launched GPT-5 today.",
    )
    story.sdlc_tags = sdlc_tags or ["ai-agents"]
    if has_summary:
        story.summary = StorySummary(
            what_happened="GPT-5 launched with enterprise API.",
            enterprise_impact="Enterprises can integrate GPT-5.",
            software_delivery_impact="Dev pipelines improve.",
            developer_impact="New endpoints available.",
            human_impact="Society benefits from better AI.",
            how_to_use="Upgrade your OpenAI SDK.",
        )
    return story


def test_story_article_written(tmp_path):
    story = _make_story()
    paths = write_story_articles([story], tmp_path)

    assert len(paths) == 1
    content = paths[0].read_text(encoding="utf-8")
    assert "GPT-5" in content
    assert "## What Happened" in content
    assert "enterprise API" in content
    assert "## How To Use" in content


def test_story_article_no_llm_call(tmp_path):
    """write_story_articles is pure Python — it takes no client parameter."""
    import inspect
    from pipeline.wiki import write_story_articles as fn
    sig = inspect.signature(fn)
    assert "client" not in sig.parameters


def test_story_article_skips_no_summary(tmp_path):
    story = _make_story(has_summary=False)
    paths = write_story_articles([story], tmp_path)
    assert paths == []


def test_story_article_dedupes_by_id(tmp_path):
    story = _make_story()
    # Same story twice
    paths = write_story_articles([story, story], tmp_path)
    assert len(paths) == 1


def test_index_links_all_articles(tmp_path):
    (tmp_path / "news").mkdir(parents=True)
    (tmp_path / "topics").mkdir(parents=True)
    (tmp_path / "digests").mkdir(parents=True)
    (tmp_path / "news" / "gpt-5-launches.md").write_text("# GPT-5")
    (tmp_path / "topics" / "ai-agents.md").write_text("# AI Agents")
    (tmp_path / "digests" / "2026-04-11.md").write_text("# Digest")

    path = write_index(tmp_path)

    content = path.read_text(encoding="utf-8")
    assert "gpt-5-launches.md" in content
    assert "ai-agents.md" in content
    assert "2026-04-11.md" in content
    assert path == tmp_path / "index.md"
```

- [ ] **Step 2: Run tests to verify they fail**

```
pytest tests/pipeline/test_wiki.py::test_story_article_written tests/pipeline/test_wiki.py::test_story_article_no_llm_call tests/pipeline/test_wiki.py::test_story_article_skips_no_summary tests/pipeline/test_wiki.py::test_story_article_dedupes_by_id tests/pipeline/test_wiki.py::test_index_links_all_articles -v
```

Expected: `ImportError` — `pipeline.wiki` doesn't exist yet.

- [ ] **Step 3: Create pipeline/wiki.py with helpers + story + index**

```python
# pipeline/wiki.py
import json
import os
import re
import tempfile
from datetime import date, datetime
from pathlib import Path

from openai import OpenAI
from schemas.story import Story, StorySummary


# ── Helpers ──────────────────────────────────────────────────────────────────

def slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def _atomic_write(path: Path, content: str) -> None:
    """Write content to path atomically (best-effort on Windows)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(content)
        os.replace(tmp, path)
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def _format_story_article(story: Story) -> str:
    s = story.summary
    pub = story.published_at
    pub_str = pub.strftime("%Y-%m-%d") if hasattr(pub, "strftime") else str(pub)
    source = story.sources[0].name if story.sources else "Unknown"
    return "\n".join([
        f"# {story.title}",
        "",
        f"**Source:** {source}",
        f"**Published:** {pub_str}",
        f"**URL:** {story.canonical_url}",
        "",
        "## What Happened",
        s.what_happened,
        "",
        "## Enterprise Impact",
        s.enterprise_impact,
        "",
        "## Developer Impact",
        s.developer_impact,
        "",
        "## Software Delivery",
        s.software_delivery_impact,
        "",
        "## Human Impact",
        s.human_impact,
        "",
        "## How To Use",
        s.how_to_use,
    ])


# ── Story articles (no LLM) ───────────────────────────────────────────────────

def write_story_articles(stories: list[Story], wiki_dir: Path) -> list[Path]:
    """Write one markdown article per story that has a summary. No LLM calls."""
    seen: set[str] = set()
    written: list[Path] = []
    for story in stories:
        if story.id in seen or story.summary is None:
            continue
        seen.add(story.id)
        slug = slugify(story.title)
        if not slug:
            continue
        path = wiki_dir / "news" / f"{slug}.md"
        _atomic_write(path, _format_story_article(story))
        written.append(path)
    return written


# ── Index (no LLM) ────────────────────────────────────────────────────────────

def write_index(wiki_dir: Path) -> Path:
    """Scan wiki subdirectories and write wiki/index.md."""
    lines = ["# Wiki Index", ""]

    digests_dir = wiki_dir / "digests"
    if digests_dir.exists():
        digest_files = sorted(digests_dir.glob("*.md"), reverse=True)
        if digest_files:
            lines.append("## Digests")
            for f in digest_files:
                rel = f.relative_to(wiki_dir)
                lines.append(f"- [{f.stem}]({rel.as_posix()})")
            lines.append("")

    topics_dir = wiki_dir / "topics"
    if topics_dir.exists():
        topic_files = sorted(topics_dir.glob("*.md"))
        if topic_files:
            lines.append("## Topics")
            for f in topic_files:
                rel = f.relative_to(wiki_dir)
                lines.append(f"- [{f.stem}]({rel.as_posix()})")
            lines.append("")

    news_dir = wiki_dir / "news"
    if news_dir.exists():
        news_files = sorted(news_dir.glob("*.md"))
        if news_files:
            lines.append("## News Articles")
            for f in news_files:
                rel = f.relative_to(wiki_dir)
                lines.append(f"- [{f.stem}]({rel.as_posix()})")
            lines.append("")

    path = wiki_dir / "index.md"
    _atomic_write(path, "\n".join(lines))
    return path
```

*(Leave the LLM functions for Task 5 — don't add them yet.)*

- [ ] **Step 4: Run tests**

```
pytest tests/pipeline/test_wiki.py::test_story_article_written tests/pipeline/test_wiki.py::test_story_article_no_llm_call tests/pipeline/test_wiki.py::test_story_article_skips_no_summary tests/pipeline/test_wiki.py::test_story_article_dedupes_by_id tests/pipeline/test_wiki.py::test_index_links_all_articles -v
```

Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add pipeline/wiki.py tests/pipeline/test_wiki.py
git commit -m "feat: wiki.py story articles and index (pure Python)"
```

---

## Task 5: pipeline/wiki.py — LLM functions + main()

**Files:**
- Modify: `pipeline/wiki.py` (add topic articles, digest, main)
- Modify: `tests/pipeline/test_wiki.py` (add LLM tests)

- [ ] **Step 1: Add the LLM tests to tests/pipeline/test_wiki.py**

Append to the end of `tests/pipeline/test_wiki.py`:

```python
from pipeline.wiki import write_topic_articles, write_digest


def test_topic_article_written(tmp_path):
    story = _make_story(sdlc_tags=["ai-agents"])
    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = MagicMock(
        choices=[MagicMock(message=MagicMock(content="# AI Agents\n\nContent here."))]
    )
    paths = write_topic_articles([story], tmp_path, mock_client, "gemma3")

    assert len(paths) == 1
    assert paths[0].name == "ai-agents.md"
    assert "AI Agents" in paths[0].read_text(encoding="utf-8")


def test_topic_article_failure_skips(tmp_path):
    story = _make_story(sdlc_tags=["tooling"])
    mock_client = MagicMock()
    mock_client.chat.completions.create.side_effect = Exception("LLM unavailable")

    # Must not raise — just skip and return empty list
    paths = write_topic_articles([story], tmp_path, mock_client, "gemma3")
    assert paths == []


def test_digest_date_stamped(tmp_path):
    story = _make_story()
    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = MagicMock(
        choices=[MagicMock(message=MagicMock(content="# Weekly Digest\n\nContent."))]
    )
    today = date.today().isoformat()

    path = write_digest([story], tmp_path, mock_client, "gemma3")

    assert path is not None
    assert path.name == f"{today}.md"
    assert "Weekly Digest" in path.read_text(encoding="utf-8")


def test_digest_failure_returns_none(tmp_path):
    story = _make_story()
    mock_client = MagicMock()
    mock_client.chat.completions.create.side_effect = Exception("LLM error")

    path = write_digest([story], tmp_path, mock_client, "gemma3")
    assert path is None
```

- [ ] **Step 2: Run new tests to confirm they fail (ImportError)**

```
pytest tests/pipeline/test_wiki.py::test_topic_article_written tests/pipeline/test_wiki.py::test_topic_article_failure_skips tests/pipeline/test_wiki.py::test_digest_date_stamped tests/pipeline/test_wiki.py::test_digest_failure_returns_none -v
```

Expected: `ImportError` — `write_topic_articles` and `write_digest` not yet defined.

- [ ] **Step 3: Add write_topic_articles and write_digest to pipeline/wiki.py**

Append before the final line (or before a `if __name__ == "__main__"` guard if present) in `pipeline/wiki.py`:

```python
# ── Topic articles (one LLM call per tag) ────────────────────────────────────

def write_topic_articles(
    stories: list[Story], wiki_dir: Path, client: OpenAI, model: str
) -> list[Path]:
    """Write one markdown article per unique sdlc_tag via one LLM call each."""
    tag_to_stories: dict[str, list[Story]] = {}
    seen_per_tag: dict[str, set[str]] = {}
    for story in stories:
        for tag in story.sdlc_tags:
            if tag not in tag_to_stories:
                tag_to_stories[tag] = []
                seen_per_tag[tag] = set()
            if story.id not in seen_per_tag[tag]:
                seen_per_tag[tag].add(story.id)
                tag_to_stories[tag].append(story)

    written: list[Path] = []
    for tag, tag_stories in sorted(tag_to_stories.items()):
        slug = slugify(tag)
        if not slug:
            continue
        path = wiki_dir / "topics" / f"{slug}.md"
        story_lines = "\n".join(
            f"- {s.title}: {s.summary.what_happened if s.summary else s.title}"
            for s in tag_stories
        )
        prompt = (
            f"Write a concise wiki article (200-300 words) about '{tag}' in software delivery and AI.\n"
            f"Synthesise insights from these recent stories:\n\n{story_lines}\n\n"
            f"Format as markdown with a # heading and 2-3 short sections. "
            f"Do not wrap output in a code block."
        )
        try:
            response = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
            )
            content = response.choices[0].message.content.strip()
            _atomic_write(path, content)
            written.append(path)
        except Exception as e:
            print(f"  Warning: topic article failed for '{tag}': {e}")
    return written


# ── Digest (one LLM call from top3) ──────────────────────────────────────────

def write_digest(
    top3: list[Story], wiki_dir: Path, client: OpenAI, model: str
) -> Path | None:
    """Write a weekly digest article from the top 3 stories."""
    if not top3:
        return None
    today = date.today().isoformat()
    path = wiki_dir / "digests" / f"{today}.md"
    story_lines = "\n".join(
        f"- {s.title}: {s.summary.what_happened if s.summary else s.title}"
        for s in top3
    )
    prompt = (
        f"Write a weekly digest article (200-300 words) summarising the top AI and "
        f"software delivery stories for {today}.\n"
        f"Stories:\n\n{story_lines}\n\n"
        f"Format as markdown with a # heading and a short narrative. "
        f"Do not wrap output in a code block."
    )
    try:
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
        )
        content = response.choices[0].message.content.strip()
        _atomic_write(path, content)
        return path
    except Exception as e:
        print(f"  Warning: digest failed: {e}")
        return None
```

Then add `main()` at the end of `pipeline/wiki.py`:

```python
# ── Orchestration ─────────────────────────────────────────────────────────────

def main() -> None:
    from pipeline import llm_config

    wiki_dir = Path(os.environ.get("WIKI_DIR", "D:/myprojects/wiki"))
    data_path = Path("data/summarized.json")

    raw = json.loads(data_path.read_text(encoding="utf-8"))

    def _story(d: dict) -> Story:
        if isinstance(d.get("published_at"), str):
            d["published_at"] = datetime.fromisoformat(d["published_at"])
        return Story(**d)

    top3 = [_story(s) for s in raw.get("top3", [])]
    categories: dict[str, list[Story]] = {
        cat: [_story(s) for s in stories]
        for cat, stories in raw.get("categories", {}).items()
    }

    # Collect unique stories for topic articles
    all_stories: dict[str, Story] = {}
    for s in top3:
        all_stories[s.id] = s
    for stories in categories.values():
        for s in stories:
            all_stories.setdefault(s.id, s)
    all_unique = list(all_stories.values())

    client, model = llm_config.get_client("wiki")

    print("Writing story articles...")
    story_paths = write_story_articles(all_unique, wiki_dir)
    for p in story_paths:
        print(f"  {p}")

    print("Writing topic articles...")
    topic_paths = write_topic_articles(all_unique, wiki_dir, client, model)
    for p in topic_paths:
        print(f"  {p}")

    print("Writing digest...")
    digest_path = write_digest(top3, wiki_dir, client, model)
    if digest_path:
        print(f"  {digest_path}")

    print("Writing index...")
    index_path = write_index(wiki_dir)
    print(f"  {index_path}")
    print("Done.")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run all wiki tests**

```
pytest tests/pipeline/test_wiki.py -v
```

Expected: all 9 tests pass.

- [ ] **Step 5: Commit**

```bash
git add pipeline/wiki.py tests/pipeline/test_wiki.py
git commit -m "feat: wiki.py topic articles, digest, and main() orchestration"
```

---

## Task 6: pipeline/run.py

**Files:**
- Create: `pipeline/run.py`
- Create: `tests/pipeline/test_run.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/pipeline/test_run.py
import sys
import pytest
from unittest.mock import patch


def test_run_exits_on_ollama_unavailable(monkeypatch):
    """When LLM_BACKEND=local and Ollama is unreachable, main() must exit(1)."""
    monkeypatch.setenv("LLM_BACKEND", "local")
    # Force fresh llm_config load so LLM_BACKEND=local takes effect
    monkeypatch.delitem(sys.modules, "pipeline.llm_config", raising=False)

    with patch("pipeline.run._ping_ollama", return_value=False):
        with pytest.raises(SystemExit) as exc:
            from pipeline import run
            # Reload run so it picks up fresh llm_config on next main() call
            import importlib
            importlib.reload(run)
            run.main()

    assert exc.value.code == 1
```

- [ ] **Step 2: Run test to verify it fails**

```
pytest tests/pipeline/test_run.py -v
```

Expected: `ModuleNotFoundError` — `pipeline.run` doesn't exist.

- [ ] **Step 3: Create pipeline/run.py**

```python
# pipeline/run.py
"""Local full-pipeline runner. Chains all steps including wiki.

Usage:
    LLM_BACKEND=local python -m pipeline.run
"""
import importlib
import sys


def _ping_ollama(base_url: str = "http://localhost:11434") -> bool:
    """Return True if Ollama is reachable at the given base URL."""
    try:
        import httpx
        resp = httpx.get(f"{base_url}/api/tags", timeout=5)
        return resp.status_code == 200
    except Exception:
        return False


def main() -> None:
    from pipeline import llm_config
    import os

    if llm_config.LLM_BACKEND == "local":
        ollama_url = os.environ.get("OLLAMA_URL", "http://localhost:11434")
        print(f"Pinging Ollama at {ollama_url}...")
        if not _ping_ollama(ollama_url):
            print(
                f"Error: Ollama is not reachable at {ollama_url}.\n"
                f"Start it with: ollama serve"
            )
            sys.exit(1)
        print("  Ollama is available.")

    steps = [
        ("fetch", "pipeline.fetch"),
        ("normalize", "pipeline.normalize"),
        ("rank", "pipeline.rank"),
        ("summarize", "pipeline.summarize"),
        ("wiki", "pipeline.wiki"),
    ]

    for name, module_path in steps:
        print(f"\nRunning {name}...")
        try:
            mod = importlib.import_module(module_path)
            mod.main()
        except Exception as e:
            print(f"Error in {name}: {e}")
            sys.exit(1)


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run the test**

```
pytest tests/pipeline/test_run.py -v
```

Expected: 1 passed.

- [ ] **Step 5: Run the full test suite**

```
pytest tests/ -v --tb=short
```

Expected: all tests pass (no regressions across all pipeline tests).

- [ ] **Step 6: Commit**

```bash
git add pipeline/run.py tests/pipeline/test_run.py
git commit -m "feat: pipeline/run.py local runner with Ollama availability check"
```

---

## Final Verification

- [ ] **Run full test suite one last time**

```
cd D:/myprojects/newsletteragent
pytest tests/ -v
```

Expected: all tests pass.

- [ ] **Smoke test locally (optional — requires Ollama running)**

```
LLM_BACKEND=local python -m pipeline.wiki
```

Expected output:
```
Writing story articles...
  D:\myprojects\wiki\news\<slug>.md
Writing topic articles...
  D:\myprojects\wiki\topics\<tag>.md
Writing digest...
  D:\myprojects\wiki\digests\YYYY-MM-DD.md
Writing index...
  D:\myprojects\wiki\index.md
Done.
```

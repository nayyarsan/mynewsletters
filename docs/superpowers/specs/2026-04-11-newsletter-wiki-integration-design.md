# Newsletter Wiki Integration — Design Spec
_Date: 2026-04-11_

## Overview

Add wiki integration to the newsletteragent pipeline. A new `pipeline/wiki.py` step reads `data/summarized.json` and writes structured markdown articles to `D:/myprojects/wiki/` (the shared private wiki). A new `pipeline/llm_config.py` module centralises LLM backend selection, enabling the full pipeline to run locally with Gemma3 via Ollama (`LLM_BACKEND=local`) or in CI with GitHub Models (`LLM_BACKEND=github`, default).

---

## Goals

1. Stories from the newsletter feed into the shared wiki alongside discoveryandresearch repo articles
2. A single env var (`LLM_BACKEND`) switches the entire pipeline between local Gemma3 and CI GPT-4o — no code changes required
3. CI behaviour is unchanged (no `LLM_BACKEND` set → defaults to `github`)

---

## New Files

| File | Responsibility |
|---|---|
| `pipeline/llm_config.py` | Central LLM config — `get_client(step)` returns `(OpenAI, model_name)` |
| `pipeline/wiki.py` | Wiki build step — reads `summarized.json`, writes to `D:/myprojects/wiki/` |
| `pipeline/run.py` | Local full-pipeline runner — chains all steps including wiki |
| `tests/pipeline/test_llm_config.py` | Unit tests for llm_config |
| `tests/pipeline/test_wiki.py` | Unit tests for wiki step |
| `tests/pipeline/test_run.py` | Unit test for run.py Ollama availability check |

## Modified Files

| File | Change |
|---|---|
| `pipeline/rank.py` | Replace hardcoded `get_client()` with `llm_config.get_client("rank")` |
| `pipeline/summarize.py` | Replace hardcoded `get_client()` with `llm_config.get_client("summarize")` |
| `tests/pipeline/test_rank.py` | Update mock target to `pipeline.llm_config.get_client` |
| `tests/pipeline/test_summarize.py` | Update mock target to `pipeline.llm_config.get_client` |

---

## `pipeline/llm_config.py`

```python
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
    raise ValueError(f"Unknown LLM_BACKEND '{LLM_BACKEND}'. Must be one of: {list(BACKENDS)}")


def get_client(step: str) -> tuple[OpenAI, str]:
    """Return (OpenAI client, model name) for the given pipeline step."""
    backend = BACKENDS[LLM_BACKEND]
    client = OpenAI(base_url=backend["base_url"], api_key=backend["api_key"])
    return client, backend["models"][step]
```

---

## Wiki Data Flow

```
data/summarized.json
├── top3              list[Story] with full StorySummary
├── categories        dict[str, list[Story]] by priority_category
└── enterprise_items  list[Story]
        │
        ▼
1. STORY ARTICLES  — pure Python, NO LLM call
   All stories from top3 + categories, deduped by Story.id
   Format StorySummary fields directly into markdown sections:
   What Happened / Enterprise Impact / Developer Impact /
   Software Delivery / Human Impact / How To Use
   → wiki/news/<story-slug>.md

2. TOPIC ARTICLES  — one LLM call per unique sdlc_tag
   Group stories by sdlc_tags, pass titles + what_happened to LLM
   → wiki/topics/<tag-slug>.md

3. DIGEST  — one LLM call from top3
   Pass top3 titles + summaries to LLM for weekly narrative
   → wiki/digests/YYYY-MM-DD.md

4. INDEX  — pure Python, no LLM call
   Scan wiki/news/, wiki/topics/, wiki/digests/
   → wiki/index.md
```

Wiki output path: `WIKI_DIR` env var, default `D:/myprojects/wiki/`.
News articles go to `wiki/news/` — no collision with discoveryandresearch `wiki/repos/`.

---

## `pipeline/run.py` (local runner)

```bash
LLM_BACKEND=local python -m pipeline.run
```

Steps in order:
1. If `LLM_BACKEND=local`: ping `http://localhost:11434/api/tags` — exit with clear message if unreachable
2. `pipeline.fetch.main()`
3. `pipeline.normalize.main()`
4. `pipeline.rank.main()`
5. `pipeline.summarize.main()`
6. `pipeline.wiki.main()`

Each step's `main()` called directly. Any unhandled exception → print error, `sys.exit(1)`.

---

## Error Handling

- **Unknown `LLM_BACKEND`** — `ValueError` raised at module import time (fail fast)
- **Ollama unavailable** — ping at `run.py` startup when `LLM_BACKEND=local`; exit before any step runs
- **Per-LLM-call failures** — topic articles and digest: log warning, skip, continue. Story articles never fail (no LLM).
- **Step failures in `run.py`** — caught at top level, print error, `sys.exit(1)`
- **Existing rank/summarize error handling** — unchanged

---

## Testing

### `tests/pipeline/test_llm_config.py`

| Test | What it covers |
|---|---|
| `test_github_backend_is_default` | No env var → GitHub Models base_url, correct models per step |
| `test_local_backend` | `LLM_BACKEND=local` → Ollama base_url, `gemma3` for all steps |
| `test_unknown_backend_raises` | `LLM_BACKEND=bogus` → `ValueError` |

### `tests/pipeline/test_wiki.py`

| Test | What it covers |
|---|---|
| `test_story_article_written` | StorySummary → formatted markdown at `wiki/news/<slug>.md` |
| `test_story_article_no_llm_call` | Story articles do NOT call `client.chat` |
| `test_topic_article_written` | Stories with sdlc_tags → `wiki/topics/<tag>.md` via mocked LLM |
| `test_topic_article_failure_skips` | LLM failure → skip topic, continue |
| `test_digest_date_stamped` | Digest → `wiki/digests/YYYY-MM-DD.md` |
| `test_index_links_all_articles` | Wiki dir with files → `index.md` contains all links |

### `tests/pipeline/test_run.py`

| Test | What it covers |
|---|---|
| `test_run_exits_on_ollama_unavailable` | `LLM_BACKEND=local` + Ollama unreachable → `sys.exit(1)` before any step |

### Modified existing tests

- `tests/pipeline/test_rank.py` — update mock target from `pipeline.rank.OpenAI` → `pipeline.llm_config.get_client`
- `tests/pipeline/test_summarize.py` — same update

---

## Out of Scope

- Cross-referencing new stories against existing wiki articles
- Modifying the CI GitHub Actions workflow
- Changes to `publish.py` or `deliver.py`
- Running wiki step in CI (wiki remains local-only)

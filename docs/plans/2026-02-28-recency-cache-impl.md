# Recency Filtering + Summary Cache — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Prevent stale stories from dominating the digest by adding a 14-day hard cutoff + 8–14 day decay, and save LLM costs by caching summaries keyed by URL between runs.

**Architecture:** `recency_multiplier()` is added to `rank.py` and imported by `summarize.py`. The 14-day cutoff runs at the start of `rank.py main()`. Decay is applied in `heuristic_prescore()`, `select_top_stories()`, and `pick_top3()`. Summary cache is a JSON file persisted between GitHub Actions runs via `actions/cache`.

**Tech Stack:** Python 3.12, pytest, GitHub Actions `actions/cache@v4`

---

### Task 1: Add `recency_multiplier()` + 14-day cutoff to `rank.py`

**Files:**
- Modify: `pipeline/rank.py`
- Test: `tests/pipeline/test_rank.py`

**Step 1: Run existing tests to confirm green baseline**

```bash
cd D:/myprojects/newsletteragent && python -m pytest tests/pipeline/test_rank.py -v
```

Expected: All 7 tests PASS.

**Step 2: Add failing tests for recency behaviour**

Add to `tests/pipeline/test_rank.py` (append after existing tests):

```python
from datetime import timedelta
from pipeline.rank import recency_multiplier, PRESCORE_LIMIT


def test_recency_multiplier_fresh_story():
    pub = datetime.now(tz=timezone.utc) - timedelta(days=3)
    assert recency_multiplier(pub) == 1.0


def test_recency_multiplier_week_old():
    pub = datetime.now(tz=timezone.utc) - timedelta(days=7)
    assert recency_multiplier(pub) == 1.0


def test_recency_multiplier_ten_days_old():
    pub = datetime.now(tz=timezone.utc) - timedelta(days=10)
    assert recency_multiplier(pub) == 0.5


def test_recency_multiplier_naive_datetime():
    """Naive datetimes (no tzinfo) must be handled without raising."""
    pub = datetime.now() - timedelta(days=3)
    assert recency_multiplier(pub) == 1.0


def test_heuristic_prescore_decays_old_story():
    fresh = Story.from_url(
        url="https://example.com/fresh",
        title="Enterprise agent platform",
        source_name="test",
        published_at=datetime.now(tz=timezone.utc) - timedelta(days=2),
        raw_content="test",
    )
    old = Story.from_url(
        url="https://example.com/old",
        title="Enterprise agent platform",
        source_name="test",
        published_at=datetime.now(tz=timezone.utc) - timedelta(days=10),
        raw_content="test",
    )
    assert heuristic_prescore(fresh, {}) > heuristic_prescore(old, {})


def test_14_day_cutoff_in_main(monkeypatch, tmp_path):
    """Stories older than 14 days must be dropped before ranking."""
    import json
    from pathlib import Path
    from pipeline import rank as mod

    fresh_story = {
        "id": "fresh1",
        "title": "Fresh Story",
        "canonical_url": "https://example.com/fresh",
        "sources": [{"name": "Test", "url": "https://example.com/fresh"}],
        "published_at": (datetime.now(tz=timezone.utc) - timedelta(days=2)).isoformat(),
        "raw_content": "Some content.",
        "priority_category": None,
        "priority_score": None,
        "summary": None,
    }
    old_story = {
        "id": "old1",
        "title": "Old Story",
        "canonical_url": "https://example.com/old",
        "sources": [{"name": "Test", "url": "https://example.com/old"}],
        "published_at": (datetime.now(tz=timezone.utc) - timedelta(days=20)).isoformat(),
        "raw_content": "Some content.",
        "priority_category": None,
        "priority_score": None,
        "summary": None,
    }
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (data_dir / "normalized.json").write_text(json.dumps([fresh_story, old_story]))
    (tmp_path / "sources").mkdir()
    (tmp_path / "sources" / "sources.yaml").write_text("sources: []")

    seen_stories = []

    def fake_presort(stories, weights, limit=40):
        seen_stories.extend(stories)
        return []

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(mod, "presort_and_limit", fake_presort)
    monkeypatch.setattr(mod, "get_client", lambda: None)
    monkeypatch.setattr(mod, "_load_source_weights", lambda: {})

    mod.main()

    urls = [s.canonical_url for s in seen_stories]
    assert "https://example.com/fresh" in urls
    assert "https://example.com/old" not in urls


def test_select_top_stories_prefers_fresh_over_stale():
    fresh = MOCK_STORY.model_copy(deep=True)
    fresh.id = "fresh"
    fresh.priority_category = "enterprise_software_delivery"
    fresh.priority_score = 80
    fresh.published_at = datetime.now(tz=timezone.utc) - timedelta(days=2)

    stale = MOCK_STORY.model_copy(deep=True)
    stale.id = "stale"
    stale.priority_category = "enterprise_software_delivery"
    stale.priority_score = 80   # same score — recency should break the tie
    stale.published_at = datetime.now(tz=timezone.utc) - timedelta(days=10)

    result = select_top_stories([fresh, stale], per_category=2)
    ordered = result["enterprise_software_delivery"]
    assert ordered[0].id == "fresh"
    assert ordered[1].id == "stale"
```

**Step 3: Run to verify they fail**

```bash
cd D:/myprojects/newsletteragent && python -m pytest tests/pipeline/test_rank.py::test_recency_multiplier_fresh_story -v
```

Expected: FAIL — `recency_multiplier` not defined.

**Step 4: Implement changes in `pipeline/rank.py`**

Add the import at the top of the file (after existing imports):

```python
from datetime import datetime, timezone, timedelta
```

Add `recency_multiplier()` function after `_WEIGHT_SCORES` / `PRESCORE_LIMIT` constants:

```python
def recency_multiplier(published_at: datetime) -> float:
    """Return 1.0 for stories ≤7 days old, 0.5 for 8–14 days old."""
    pub = published_at if published_at.tzinfo else published_at.replace(tzinfo=timezone.utc)
    age_days = (datetime.now(tz=timezone.utc) - pub).days
    return 1.0 if age_days <= 7 else 0.5
```

Update `heuristic_prescore()` to apply the multiplier — replace the final `return score` line:

```python
    return int(score * recency_multiplier(story.published_at))
```

Update `select_top_stories()` sort key — replace the existing sort:

```python
    for cat in categorized:
        categorized[cat].sort(
            key=lambda s: (
                (s.priority_score or 0) * recency_multiplier(s.published_at),
                s.source_count,
            ),
            reverse=True,
        )
        categorized[cat] = categorized[cat][:per_category]
```

Add the 14-day cutoff at the start of `main()`, right after the stories list is built (after the `for item in stories_raw` loop):

```python
    # Drop stories older than 14 days — prevents repeat stories across weeks
    cutoff = datetime.now(tz=timezone.utc) - timedelta(days=14)
    before = len(stories)
    stories = [
        s for s in stories
        if (s.published_at if s.published_at.tzinfo else s.published_at.replace(tzinfo=timezone.utc)) >= cutoff
    ]
    print(f"  Recency filter: {before - len(stories)} stories dropped (>14 days), {len(stories)} remain")
```

**Step 5: Run all rank tests**

```bash
cd D:/myprojects/newsletteragent && python -m pytest tests/pipeline/test_rank.py -v
```

Expected: All 14 tests PASS.

**Step 6: Commit**

```bash
cd D:/myprojects/newsletteragent && git add pipeline/rank.py tests/pipeline/test_rank.py && git commit -m "feat: add 14-day cutoff and recency decay to ranking

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

### Task 2: Apply recency decay to `pick_top3()` in `summarize.py`

**Files:**
- Modify: `pipeline/summarize.py`
- Test: `tests/pipeline/test_summarize.py`

**Step 1: Run existing tests to confirm green baseline**

```bash
cd D:/myprojects/newsletteragent && python -m pytest tests/pipeline/test_summarize.py -v
```

Expected: All 4 tests PASS.

**Step 2: Add a failing test**

Add to `tests/pipeline/test_summarize.py`:

```python
from datetime import timedelta
from pipeline.rank import recency_multiplier


def test_pick_top3_prefers_fresh_over_stale():
    """A fresh story with equal score must beat a stale one for top 3."""
    fresh = MOCK_STORY.model_copy(deep=True)
    fresh.id = "fresh"
    fresh.priority_score = 80
    fresh.published_at = datetime.now(tz=timezone.utc) - timedelta(days=2)

    stale = MOCK_STORY.model_copy(deep=True)
    stale.id = "stale"
    stale.priority_score = 80
    stale.published_at = datetime.now(tz=timezone.utc) - timedelta(days=10)

    stories_by_category = {"enterprise_software_delivery": [fresh, stale]}
    top3 = pick_top3(stories_by_category)

    assert top3[0].id == "fresh"
    assert top3[1].id == "stale"
```

**Step 3: Run to verify it fails**

```bash
cd D:/myprojects/newsletteragent && python -m pytest tests/pipeline/test_summarize.py::test_pick_top3_prefers_fresh_over_stale -v
```

Expected: FAIL — `pick_top3` does not apply recency decay.

**Step 4: Update `pick_top3()` in `pipeline/summarize.py`**

Add import at the top of the file:

```python
from pipeline.rank import recency_multiplier
```

Replace the existing `pick_top3()` function:

```python
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
```

**Step 5: Run all summarize tests**

```bash
cd D:/myprojects/newsletteragent && python -m pytest tests/pipeline/test_summarize.py -v
```

Expected: All 5 tests PASS.

**Step 6: Commit**

```bash
cd D:/myprojects/newsletteragent && git add pipeline/summarize.py tests/pipeline/test_summarize.py && git commit -m "feat: apply recency decay in pick_top3

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

### Task 3: Add summary cache to `summarize.py`

**Files:**
- Modify: `pipeline/summarize.py`
- Test: `tests/pipeline/test_summarize.py`

**Step 1: Add failing tests for cache behaviour**

Add to `tests/pipeline/test_summarize.py`:

```python
from pipeline.summarize import load_cache, save_cache


def test_load_cache_returns_empty_dict_when_file_missing(tmp_path):
    cache = load_cache(tmp_path / "no_such_file.json")
    assert cache == {}


def test_load_cache_evicts_entries_older_than_14_days(tmp_path):
    import json
    old_entry = {
        "summary": {"what_happened": "old", "enterprise_impact": "x",
                     "software_delivery_impact": "x", "developer_impact": "x",
                     "human_impact": "x", "how_to_use": "x"},
        "cached_at": (datetime.now(tz=timezone.utc) - timedelta(days=20)).isoformat(),
    }
    fresh_entry = {
        "summary": {"what_happened": "fresh", "enterprise_impact": "x",
                    "software_delivery_impact": "x", "developer_impact": "x",
                    "human_impact": "x", "how_to_use": "x"},
        "cached_at": (datetime.now(tz=timezone.utc) - timedelta(days=2)).isoformat(),
    }
    cache_file = tmp_path / "summary_cache.json"
    cache_file.write_text(json.dumps({
        "https://old.com": old_entry,
        "https://fresh.com": fresh_entry,
    }))

    cache = load_cache(cache_file)
    assert "https://old.com" not in cache
    assert "https://fresh.com" in cache


def test_save_cache_writes_json(tmp_path):
    cache = {"https://example.com": {"summary": {}, "cached_at": "2026-02-28T00:00:00+00:00"}}
    path = tmp_path / "data" / "summary_cache.json"
    save_cache(cache, path)
    assert path.exists()
    import json
    assert json.loads(path.read_text()) == cache


def test_summarize_story_uses_cache_hit():
    cache = {
        "https://openai.com/gpt-5": {
            "summary": {
                "what_happened": "Cached summary.",
                "enterprise_impact": "Cached impact.",
                "software_delivery_impact": "Cached delivery.",
                "developer_impact": "Cached dev.",
                "human_impact": "Cached human.",
                "how_to_use": "Cached use.",
            },
            "cached_at": datetime.now(tz=timezone.utc).isoformat(),
        }
    }
    mock_client = MagicMock()
    story = MOCK_STORY.model_copy(deep=True)

    result = summarize_story(story, mock_client, cache=cache)

    # LLM must NOT be called
    mock_client.chat.completions.create.assert_not_called()
    assert result.summary is not None
    assert result.summary.what_happened == "Cached summary."


def test_summarize_story_populates_cache_on_miss():
    cache = {}
    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = MagicMock(
        choices=[MagicMock(message=MagicMock(content=MOCK_SUMMARY))]
    )
    story = MOCK_STORY.model_copy(deep=True)

    summarize_story(story, mock_client, cache=cache)

    assert "https://openai.com/gpt-5" in cache
    assert "cached_at" in cache["https://openai.com/gpt-5"]
    assert cache["https://openai.com/gpt-5"]["summary"]["what_happened"] != ""
```

**Step 2: Run to verify they fail**

```bash
cd D:/myprojects/newsletteragent && python -m pytest tests/pipeline/test_summarize.py::test_load_cache_returns_empty_dict_when_file_missing -v
```

Expected: FAIL — `load_cache` not defined.

**Step 3: Implement cache in `pipeline/summarize.py`**

Add imports at the top (after existing imports):

```python
from datetime import datetime, timezone, timedelta
from pathlib import Path
```

Add cache constants and functions after the existing prompts:

```python
CACHE_PATH = Path("data/summary_cache.json")
CACHE_MAX_DAYS = 14


def load_cache(path: Path = CACHE_PATH) -> dict:
    """Load summary cache, evicting entries older than CACHE_MAX_DAYS."""
    if not path.exists():
        return {}
    try:
        raw = json.loads(path.read_text())
        cutoff = datetime.now(tz=timezone.utc) - timedelta(days=CACHE_MAX_DAYS)
        return {
            url: entry for url, entry in raw.items()
            if datetime.fromisoformat(entry["cached_at"]) >= cutoff
        }
    except Exception:
        return {}


def save_cache(cache: dict, path: Path = CACHE_PATH) -> None:
    """Persist summary cache to disk."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(cache, indent=2))
```

Update `summarize_story()` signature and body — replace the existing function:

```python
def summarize_story(story: Story, client: OpenAI, cache: dict | None = None) -> Story:
    # Check cache first — skip LLM if we already have a summary for this URL
    if cache is not None and story.canonical_url in cache:
        print(f"  Cache hit: {story.title[:50]}")
        story.summary = StorySummary(**cache[story.canonical_url]["summary"])
        return story

    sources_str = " | ".join(s.name for s in story.sources)
    prompt = SUMMARIZE_USER_PROMPT.format(
        title=story.title,
        sources=sources_str,
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
```

Update `main()` to load and save cache — replace the two lines after `client = get_client()`:

```python
def main():
    client = get_client()
    cache = load_cache()
    print(f"  Loaded {len(cache)} cached summaries")

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
    top3 = [summarize_story(s, client, cache) for s in top3]

    save_cache(cache)
    print(f"  Saved {len(cache)} summaries to cache")

    output = {
        "top3": [s.model_dump(mode="json") for s in top3],
        "categories": {
            cat: [s.model_dump(mode="json") for s in stories]
            for cat, stories in stories_by_category.items()
        },
    }
    Path("data/summarized.json").write_text(json.dumps(output, indent=2, default=str))
    print("  Saved to data/summarized.json")
```

**Step 4: Run all summarize tests**

```bash
cd D:/myprojects/newsletteragent && python -m pytest tests/pipeline/test_summarize.py -v
```

Expected: All 10 tests PASS.

**Step 5: Run full suite to catch regressions**

```bash
cd D:/myprojects/newsletteragent && python -m pytest tests/ -v --ignore=tests/scrapers
```

Expected: All tests PASS.

**Step 6: Commit**

```bash
cd D:/myprojects/newsletteragent && git add pipeline/summarize.py tests/pipeline/test_summarize.py && git commit -m "feat: add summary cache with 14-day eviction

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

### Task 4: Add `actions/cache` to the workflow

**Files:**
- Modify: `.github/workflows/newsletter.yml`

No tests for this task — verify by inspecting the YAML and triggering a run.

**Step 1: Add cache restore + save to the `summarize` job**

In `.github/workflows/newsletter.yml`, replace the `summarize` job with:

```yaml
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
      - name: Restore summary cache
        uses: actions/cache@v4
        with:
          path: data/summary_cache.json
          key: summary-cache-v1-${{ github.run_id }}
          restore-keys: |
            summary-cache-v1-
      - name: Summarize stories
        run: python pipeline/summarize.py
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
      - uses: actions/upload-artifact@v4
        with:
          name: summarized
          path: data/summarized.json
```

Note: `actions/cache@v4` automatically saves the cache in a post-step after the job completes — no explicit save step needed.

**Step 2: Verify the YAML is valid**

```bash
cd D:/myprojects/newsletteragent && python -c "import yaml; yaml.safe_load(open('.github/workflows/newsletter.yml'))" && echo "YAML valid"
```

Expected: `YAML valid`

**Step 3: Commit and push**

```bash
cd D:/myprojects/newsletteragent && git add .github/workflows/newsletter.yml && git commit -m "ci: add actions/cache to persist summary cache between runs

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

```bash
cd D:/myprojects/newsletteragent && git push origin master
```

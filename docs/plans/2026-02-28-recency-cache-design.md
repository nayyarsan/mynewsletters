# Recency Filtering + Summary Cache — Design

**Date:** 2026-02-28
**Scope:** Add 14-day hard cutoff, 8–14 day recency decay, and URL-keyed summary cache

---

## Problem

1. **Stale stories repeat** — stories older than 14 days score well on source weight and keywords, making them top picks week after week even when fresh stories exist.
2. **Wasted LLM calls** — the same story URLs can recur across runs (e.g. a story that was ranked but not top-3 last week may appear again), causing `gpt-4o` to re-summarize content it has already analysed.

---

## Approved Design

### Feature 1 — Recency filtering (`pipeline/rank.py`, `pipeline/summarize.py`)

**Hard 14-day cutoff** — applied at the start of `rank.py main()` before any scoring:
```python
cutoff = datetime.now(tz=timezone.utc) - timedelta(days=14)
stories = [s for s in stories if s.published_at.replace(tzinfo=...) >= cutoff]
```
Log how many stories are dropped. Stories older than 14 days never reach the LLM.

**Recency decay multiplier** — applied in three places:

| Location | Effect |
|----------|--------|
| `heuristic_prescore()` | Older stories lose pre-filter slots to fresh ones |
| `select_top_stories()` | Older stories rank below fresh ones in final category sort |
| `pick_top3()` in `summarize.py` | Older stories can't be top-3 picks |

Decay formula:
```python
def recency_multiplier(published_at: datetime) -> float:
    age_days = (datetime.now(tz=timezone.utc) - published_at.astimezone(timezone.utc)).days
    if age_days <= 7:
        return 1.0
    return 0.5   # 8–14 days old
```

### Feature 2 — Summary cache (`data/summary_cache.json`)

**Cache file format:**
```json
{
  "https://example.com/story": {
    "summary": { "what_happened": "...", ... },
    "cached_at": "2026-02-28T00:00:00Z"
  }
}
```

**`summarize.py` changes:**
- Load cache on startup (empty dict if file missing)
- Before each `gpt-4o` call: check if `story.canonical_url` is in cache
  - Cache hit → use cached `StorySummary`, skip API call, log "cache hit"
  - Cache miss → call `gpt-4o`, store result in cache
- On shutdown: write updated cache back to `data/summary_cache.json`
- **Cache eviction on load**: drop entries where `cached_at < now - 14 days` (aligns with recency cutoff — no point keeping summaries for stories we'd filter out anyway)

**Workflow changes (`.github/workflows/newsletter.yml`):**
Add `actions/cache` steps to the `summarize` job:
```yaml
- uses: actions/cache@v4
  with:
    path: data/summary_cache.json
    key: summary-cache-v1-${{ github.run_id }}
    restore-keys: |
      summary-cache-v1-
```
This restores the most recent cache before summarizing and saves the updated cache after.

---

## Files Changed

| File | Change |
|------|--------|
| `pipeline/rank.py` | 14-day cutoff in `main()`, `recency_multiplier()` helper, decay in `heuristic_prescore()` and `select_top_stories()` |
| `pipeline/summarize.py` | `recency_multiplier()` in `pick_top3()`, cache load/save/evict, cache lookup in `summarize_story()` |
| `.github/workflows/newsletter.yml` | `actions/cache` restore + save steps in `summarize` job |
| `tests/pipeline/test_rank.py` | Tests for `recency_multiplier()`, 14-day cutoff, decay in prescore and select |
| `tests/pipeline/test_summarize.py` | Tests for cache hit/miss, cache eviction, cache persistence |

---

## Out of Scope

- Changing the decay formula (e.g. smooth exponential) — binary 0.5× is sufficient
- Caching rank scores — only summaries are cached (rank is cheap, summarize is not)
- Storing cache in git — GitHub Actions cache is cleaner

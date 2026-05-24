"""
Offline test harness for proposed normalize-stage improvements.

Runs three candidate filters against a real normalized.json corpus
(downloaded from a recent workflow run via `gh run download`) and
prints before/after counts plus samples of dropped items so you can
sanity-check that nothing real is being killed.

No LLM calls. No mutations to the pipeline. Pure diagnostic.

Usage:
    python scripts/test_filters_local.py [path/to/normalized.json] \
        [path/to/prior/summarized.json]

Defaults:
    corpus  = tmp_real_run/normalized/normalized.json
    seen    = tmp_latest/summarized.json
"""
import json
import re
import sys

# Force UTF-8 stdout on Windows so we can print non-cp1252 chars in titles.
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
except Exception:
    pass
from datetime import datetime, timezone, timedelta
from pathlib import Path


# ---- Filter A: tighter recency cutoff -------------------------------------

def filter_recency(stories: list[dict], max_age_days: int) -> tuple[list, list]:
    cutoff = datetime.now(tz=timezone.utc) - timedelta(days=max_age_days)
    kept, dropped = [], []
    for s in stories:
        pub = s.get("published_at")
        if isinstance(pub, str):
            try:
                pub_dt = datetime.fromisoformat(pub.replace("Z", "+00:00"))
            except ValueError:
                kept.append(s)
                continue
        else:
            kept.append(s)
            continue
        if pub_dt.tzinfo is None:
            pub_dt = pub_dt.replace(tzinfo=timezone.utc)
        if pub_dt >= cutoff:
            kept.append(s)
        else:
            dropped.append(s)
    return kept, dropped


# ---- Filter B: junk-title / nav-boilerplate filter ------------------------

JUNK_EXACT_TITLES = {
    "sign in", "log in", "enterprise", "skip to content",
    "weekly issues", "explore courses", "try le chat", "try studio",
    "subscribe", "menu", "navigation", "search", "home",
}
NAV_TITLE_PATTERN = re.compile(
    r"^(try |explore |weekly |sign |log |skip |subscribe|menu|search)",
    re.IGNORECASE,
)


def is_junk(story: dict) -> tuple[bool, str]:
    title = (story.get("title") or "").strip()
    title_lower = title.lower()
    content_len = len(story.get("raw_content") or "")
    word_count = len(title.split())

    if title_lower in JUNK_EXACT_TITLES:
        return True, "exact-blocklist"
    # Nav-style phrasing AND short content => junk
    if NAV_TITLE_PATTERN.match(title) and content_len < 80:
        return True, f"nav-pattern+short(content_len={content_len})"
    # Very short title AND very short content => junk
    if word_count <= 2 and content_len < 60:
        return True, f"short-title+short-content(words={word_count},content_len={content_len})"
    return False, ""


def filter_junk(stories: list[dict]) -> tuple[list, list]:
    kept, dropped = [], []
    for s in stories:
        junk, reason = is_junk(s)
        if junk:
            dropped.append((s, reason))
        else:
            kept.append(s)
    return kept, dropped


# ---- Filter C: cross-run dedup --------------------------------------------

def load_seen(seen_path: Path) -> set[str]:
    if not seen_path.exists():
        return set()
    data = json.loads(seen_path.read_text(encoding="utf-8"))
    seen: set[str] = set()
    # Plain list of URLs (e.g. tmp_runs/_seen_combined.json)
    if isinstance(data, list) and data and isinstance(data[0], str):
        return {u for u in data if u}
    if isinstance(data, dict):
        for s in data.get("top3", []) or []:
            url = s.get("canonical_url")
            if url:
                seen.add(url)
        for items in (data.get("categories") or {}).values():
            for s in items or []:
                url = s.get("canonical_url")
                if url:
                    seen.add(url)
    elif isinstance(data, list):
        for s in data:
            url = s.get("canonical_url")
            if url:
                seen.add(url)
    return seen


def filter_cross_run(stories: list[dict], seen_urls: set[str]) -> tuple[list, list]:
    kept, dropped = [], []
    for s in stories:
        if s.get("canonical_url") in seen_urls:
            dropped.append(s)
        else:
            kept.append(s)
    return kept, dropped


# ---- Reporting ------------------------------------------------------------

def print_drop_samples(label: str, dropped, limit: int = 10):
    print(f"\n  --- {label}: {len(dropped)} dropped (showing up to {limit}) ---")
    for item in dropped[:limit]:
        if isinstance(item, tuple):
            s, reason = item
            print(f"    [{reason}] {repr((s.get('title') or '')[:80])}")
        else:
            s = item
            pub = (s.get("published_at") or "")[:10]
            print(f"    [{pub}] {repr((s.get('title') or '')[:80])}")


def main():
    corpus_path = Path(sys.argv[1] if len(sys.argv) > 1
                       else "tmp_real_run/normalized/normalized.json")
    seen_path = Path(sys.argv[2] if len(sys.argv) > 2
                     else "tmp_latest/summarized.json")

    if not corpus_path.exists():
        print(f"ERROR: corpus not found: {corpus_path}")
        print("Hint: gh run download <run-id> --dir tmp_real_run")
        sys.exit(1)

    stories = json.loads(corpus_path.read_text(encoding="utf-8"))
    print(f"Corpus: {corpus_path} ({len(stories)} stories)")

    seen = load_seen(seen_path)
    print(f"Prior-run seen URLs: {len(seen)} (from {seen_path})")

    # NB: corpus is dated relative to when the run executed, so a 5-day
    # cutoff "now" may drop almost everything if the corpus is old.
    # We anchor recency against the freshest published_at in the corpus
    # to make the test meaningful regardless of corpus age.
    pub_dates = []
    for s in stories:
        p = s.get("published_at")
        if isinstance(p, str):
            try:
                pub_dates.append(datetime.fromisoformat(p.replace("Z", "+00:00")))
            except ValueError:
                pass
    if pub_dates:
        anchor = max(pub_dates)
        print(f"Recency anchor (newest item in corpus): {anchor.isoformat()}")
    else:
        anchor = datetime.now(tz=timezone.utc)

    # --- A: recency 5d (anchored) ---
    cutoff_5d = anchor - timedelta(days=5)
    cutoff_7d = anchor - timedelta(days=7)
    kept_5d, drop_5d = [], []
    kept_7d, drop_7d = [], []
    for s in stories:
        p = s.get("published_at")
        try:
            pdt = datetime.fromisoformat(p.replace("Z", "+00:00"))
        except (ValueError, AttributeError, TypeError):
            kept_5d.append(s)
            kept_7d.append(s)
            continue
        if pdt.tzinfo is None:
            pdt = pdt.replace(tzinfo=timezone.utc)
        (kept_5d if pdt >= cutoff_5d else drop_5d).append(s)
        (kept_7d if pdt >= cutoff_7d else drop_7d).append(s)

    print("\n[A] Recency filter (anchored to newest item in corpus)")
    print(f"  7-day cutoff: keep {len(kept_7d)}, drop {len(drop_7d)}")
    print(f"  5-day cutoff: keep {len(kept_5d)}, drop {len(drop_5d)}")
    print_drop_samples("Items only 5d would drop (kept by 7d)",
                       [s for s in drop_5d if s in kept_7d])

    # --- B: junk filter ---
    kept_junk, drop_junk = filter_junk(stories)
    print("\n[B] Junk-title filter")
    print(f"  keep {len(kept_junk)}, drop {len(drop_junk)}")
    print_drop_samples("junk dropped", drop_junk, limit=20)

    # --- C: cross-run dedup ---
    kept_cr, drop_cr = filter_cross_run(stories, seen)
    print("\n[C] Cross-run dedup against last run's selections")
    print(f"  keep {len(kept_cr)}, drop {len(drop_cr)}")
    print_drop_samples("cross-run duplicates", drop_cr)

    # --- Combined effect ---
    after_a = kept_5d
    after_ab_set_ids = {id(s) for s in after_a}
    after_ab = [s for s in kept_junk if id(s) in after_ab_set_ids]
    after_abc = [s for s in after_ab if s.get("canonical_url") not in seen]
    print(f"\n[Combined] start={len(stories)} -> 5d={len(after_a)} "
          f"-> +junk={len(after_ab)} -> +cross-run={len(after_abc)}")
    print(f"  total dropped: {len(stories) - len(after_abc)}")


if __name__ == "__main__":
    main()

"""
Cross-run dedup state.

Tracks URLs that have appeared in past delivered digests so the pipeline can
hide them on subsequent runs. Persisted at `state/seen.json` and committed
back to the repo by the workflow on successful delivery.

Schema (v1):
    {
      "version": 1,
      "urls": [
        {"url": "https://...", "seen_at": "2026-05-04T14:40:22+00:00"},
        ...
      ]
    }

Entries older than RETENTION_DAYS are pruned on load.
"""
import json
from datetime import datetime, timezone, timedelta
from pathlib import Path

DEFAULT_PATH = Path("state/seen.json")
RETENTION_DAYS = 30


def _now() -> datetime:
    return datetime.now(tz=timezone.utc)


def load(path: Path = DEFAULT_PATH) -> dict:
    """Load seen-state, pruning entries older than RETENTION_DAYS.

    Returns the canonical in-memory shape:
        {"version": 1, "urls": [{"url": str, "seen_at": iso}, ...]}
    """
    if not path.exists():
        return {"version": 1, "urls": []}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"version": 1, "urls": []}

    cutoff = _now() - timedelta(days=RETENTION_DAYS)
    kept = []
    for entry in data.get("urls", []):
        url = entry.get("url")
        seen_at_raw = entry.get("seen_at")
        if not url or not seen_at_raw:
            continue
        try:
            seen_at = datetime.fromisoformat(seen_at_raw.replace("Z", "+00:00"))
        except ValueError:
            continue
        if seen_at.tzinfo is None:
            seen_at = seen_at.replace(tzinfo=timezone.utc)
        if seen_at >= cutoff:
            kept.append({"url": url, "seen_at": seen_at.isoformat()})
    return {"version": 1, "urls": kept}


def seen_url_set(state: dict) -> set[str]:
    return {entry["url"] for entry in state.get("urls", []) if entry.get("url")}


def add_urls(state: dict, urls: list[str]) -> dict:
    """Merge new URLs into state. Refreshes seen_at for any that already exist."""
    now_iso = _now().isoformat()
    by_url = {entry["url"]: entry for entry in state.get("urls", [])}
    for url in urls:
        if not url:
            continue
        by_url[url] = {"url": url, "seen_at": now_iso}
    state["urls"] = list(by_url.values())
    return state


def save(state: dict, path: Path = DEFAULT_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, indent=2), encoding="utf-8")

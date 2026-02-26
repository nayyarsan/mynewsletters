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
    import os
    output_file = Path(os.environ.get("GITHUB_OUTPUT", "/dev/null"))
    with open(output_file, "a") as f:
        f.write(f"active_sources={active_json}\n")

    if not active:
        print("ERROR: No active sources found.", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()

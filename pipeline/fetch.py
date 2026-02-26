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

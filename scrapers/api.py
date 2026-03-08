import httpx
import feedparser
from datetime import datetime, timezone, timedelta
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


def fetch_reddit(source_name: str, url: str, max_age_days: int = 7) -> list[Story]:
    feedparser.USER_AGENT = HEADERS["User-Agent"]
    feed = feedparser.parse(url)

    if feed.bozo and not feed.entries:
        return []

    cutoff = datetime.now(tz=timezone.utc) - timedelta(days=max_age_days)
    stories = []
    for entry in feed.entries:
        link = getattr(entry, "link", None)
        if not link:
            continue

        title = getattr(entry, "title", "") or ""
        content = getattr(entry, "summary", "") or ""

        published_at = None
        for attr in ("published_parsed", "updated_parsed"):
            val = getattr(entry, attr, None)
            if val:
                t = val
                published_at = datetime(t[0], t[1], t[2], t[3], t[4], t[5], tzinfo=timezone.utc)
                break

        if published_at is None or published_at < cutoff:
            continue

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

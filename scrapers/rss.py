import feedparser
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
        content = getattr(entry, "summary", "") or ""
        if not content:
            content_detail = getattr(entry, "content", [{}])
            if content_detail:
                content = content_detail[0].get("value", "") or ""

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

import feedparser
from datetime import datetime, timezone, timedelta
from schemas.story import Story

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; AINewsletterBot/1.0)"}


def _parse_date(entry) -> datetime | None:
    """Return the best available publish date, or None if genuinely unknown."""
    for attr in ("published_parsed", "updated_parsed"):
        val = getattr(entry, attr, None)
        if val:
            t = val
            return datetime(t[0], t[1], t[2], t[3], t[4], t[5], tzinfo=timezone.utc)
    return None


def fetch_rss(
    source_name: str,
    url: str,
    filter_keywords: list[str] | None = None,
    max_age_days: int = 7,
) -> list[Story]:
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
        if not content:
            content_detail = getattr(entry, "content", [{}])
            if content_detail:
                content = content_detail[0].get("value", "") or ""

        # Skip entries with no parseable date — they have no reliable recency signal
        published_at = _parse_date(entry)
        if published_at is None:
            continue

        # Skip entries older than max_age_days at fetch time
        if published_at < cutoff:
            continue

        if filter_keywords:
            combined = (title + " " + content).lower()
            if not any(kw.lower() in combined for kw in filter_keywords):
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

import httpx
from datetime import datetime, timezone
from urllib.parse import urljoin
from bs4 import BeautifulSoup
from schemas.story import Story

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; AINewsletterBot/1.0)",
    "Accept": "text/html,application/xhtml+xml",
}


def fetch_html(
    source_name: str,
    url: str,
    base_url: str,
    filter_keywords: list[str] | None = None,
) -> list[Story]:
    try:
        response = httpx.get(url, headers=HEADERS, timeout=20, follow_redirects=True)
        response.raise_for_status()
    except Exception:
        return []

    soup = BeautifulSoup(response.text, "html.parser")
    stories = []

    candidates = []
    for tag in soup.find_all(["article", "div"], class_=lambda c: c and any(
        k in c.lower() for k in ["post", "article", "blog", "entry", "item"]
    )):
        candidates.append(tag)

    if not candidates:
        candidates = soup.find_all(["h2", "h3"])

    seen_urls = set()
    for candidate in candidates[:20]:
        link_tag = candidate.find("a", href=True) if candidate.name != "a" else candidate
        if not link_tag:
            continue

        href = link_tag.get("href", "")
        full_url = urljoin(base_url, href)

        if full_url in seen_urls or not full_url.startswith("http"):
            continue
        seen_urls.add(full_url)

        title = link_tag.get_text(strip=True)
        if not title or len(title) < 5:
            continue

        parent = link_tag.parent
        content = parent.get_text(separator=" ", strip=True)[:2000] if parent else title

        if filter_keywords:
            combined = (title + " " + content).lower()
            if not any(kw.lower() in combined for kw in filter_keywords):
                continue

        stories.append(
            Story.from_url(
                url=full_url,
                title=title,
                source_name=source_name,
                published_at=datetime.now(tz=timezone.utc),
                raw_content=content,
            )
        )

    return stories

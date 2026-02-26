import pytest
import respx
import httpx
from scrapers.html import fetch_html

SAMPLE_HTML = """
<html><body>
  <article>
    <h2><a href="/blog/post-1">AI agents take over enterprise</a></h2>
    <p>Cognition released a new version of Devin today.</p>
  </article>
  <article>
    <h2><a href="/blog/post-2">New cursor feature ships</a></h2>
    <p>Cursor released background agents.</p>
  </article>
</body></html>
"""


@respx.mock
def test_fetch_html_returns_stories():
    respx.get("https://cognition.ai/blog").mock(
        return_value=httpx.Response(200, text=SAMPLE_HTML)
    )
    stories = fetch_html(
        source_name="Cognition",
        url="https://cognition.ai/blog",
        base_url="https://cognition.ai",
    )
    assert len(stories) >= 1
    assert any("AI agents" in s.title or "Devin" in s.raw_content for s in stories)


@respx.mock
def test_fetch_html_handles_404():
    respx.get("https://cognition.ai/blog").mock(
        return_value=httpx.Response(404)
    )
    stories = fetch_html(
        source_name="Cognition",
        url="https://cognition.ai/blog",
        base_url="https://cognition.ai",
    )
    assert stories == []


@respx.mock
def test_fetch_html_handles_connection_error():
    respx.get("https://cognition.ai/blog").mock(
        side_effect=httpx.ConnectError("timeout")
    )
    stories = fetch_html(
        source_name="Cognition",
        url="https://cognition.ai/blog",
        base_url="https://cognition.ai",
    )
    assert stories == []

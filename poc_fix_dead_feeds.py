"""
POC: Find correct RSS URLs for dead feeds
Tests alternative URLs for each dead source.
"""

import feedparser
import httpx

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; NewsletterBot/1.0)"}

ALTERNATIVES = {
    "Andrew Ng (The Batch)": [
        "https://www.deeplearning.ai/the-batch/",          # scrape fallback
        "https://www.deeplearning.ai/feed/",
        "https://deeplearning.ai/the-batch/feed/",
    ],
    "Anthropic": [
        "https://www.anthropic.com/rss.xml",
        "https://anthropic.com/news/rss",
        "https://www.anthropic.com/feed.xml",
    ],
    "Yann LeCun / Meta AI": [
        "https://ai.meta.com/blog/",                       # scrape fallback
        "https://engineering.fb.com/feed/",               # Meta Engineering RSS
        "https://research.facebook.com/feed/",
    ],
    "ServiceNow AI": [
        "https://www.servicenow.com/blogs/feed.xml",
        "https://www.servicenow.com/blogs/rss.xml",
        "https://www.servicenow.com/blogs/category/ai.xml",
    ],
    "Windsurf (Codeium)": [
        "https://codeium.com/blog/rss",
        "https://codeium.com/feed.xml",
        "https://codeium.com/blog/feed",
        "https://windsurf.com/blog/rss.xml",
    ],
    "Replit": [
        "https://blog.replit.com/feed.xml",
        "https://blog.replit.com/atom.xml",
        "https://replit.com/blog/rss.xml",
    ],
    "TLDR AI": [
        "https://tldr.tech/api/rss/ai",
        "https://api.tldr.tech/rss/ai",
        "https://feeds.feedburner.com/TLDRAI",
    ],
    "SAP AI": [
        "https://news.sap.com/feed/",
        "https://www.sap.com/blogs/feed.xml",
        "https://blogs.sap.com/feed/",
        "https://community.sap.com/t5/forums/rss/board-id/technology-blog-sap",
    ],
    "Azure AI": [
        "https://techcommunity.microsoft.com/t5/ai-azure-ai-services-blog/bg-p/Azure-AI-Services-Blog/rss/RSSFeedPage",
        "https://azure.microsoft.com/en-us/blog/feed/",
        "https://azure.microsoft.com/en-gb/blog/feed/",
        "https://devblogs.microsoft.com/azure-ai/feed/",
    ],
    "Mistral AI": [
        "https://mistral.ai/news/feed.xml",
        "https://mistral.ai/feed.xml",
        "https://mistral.ai/news/",                       # scrape fallback
    ],
    "xAI Blog": [
        "https://x.ai/news/rss.xml",
        "https://x.ai/feed.xml",
        "https://x.ai/blog/rss",
        "https://x.ai/blog",                              # scrape fallback
    ],
}

def try_rss(url):
    try:
        feed = feedparser.parse(url)
        if not feed.bozo and feed.entries:
            return True, len(feed.entries), feed.entries[0].get("title", "")[:60]
    except:
        pass
    return False, 0, ""

def try_http(url):
    try:
        r = httpx.get(url, headers=HEADERS, timeout=10, follow_redirects=True)
        return r.status_code == 200, r.status_code
    except:
        return False, 0

print("\nSearching for working alternative URLs...\n")
print("-" * 100)

findings = {}

for source, urls in ALTERNATIVES.items():
    print(f"\n{source}:")
    found = False
    for url in urls:
        is_rss, count, title = try_rss(url)
        if is_rss:
            print(f"  [RSS OK]    {url}  ({count} items) — {title}")
            findings[source] = {"url": url, "type": "rss", "items": count}
            found = True
            break
        else:
            ok, status = try_http(url)
            if ok:
                print(f"  [HTTP OK]   {url}  (HTTP {status}) — scrape fallback")
                if source not in findings:
                    findings[source] = {"url": url, "type": "scrape"}
            else:
                print(f"  [DEAD]      {url}  (HTTP {status})")

    if not found and source not in findings:
        print(f"  [NO SOLUTION FOUND] — needs manual investigation")

print("\n" + "=" * 100)
print("\nRECOMMENDED SOURCE UPDATES:")
print("-" * 100)
for source, info in findings.items():
    print(f"  {source:<35} {info['type']:<8} {info['url']}")

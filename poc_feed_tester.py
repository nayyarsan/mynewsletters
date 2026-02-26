"""
POC: RSS Feed & Source Validator
Tests all identified sources and reports live/dead/parseable status.
"""

import feedparser
import httpx
import json
import time
from datetime import datetime

SOURCES = [
    # --- INFLUENCERS ---
    {"name": "Andrej Karpathy",          "type": "rss",    "url": "https://karpathy.github.io/feed.xml"},
    {"name": "Andrew Ng (The Batch)",    "type": "rss",    "url": "https://www.deeplearning.ai/the-batch/feed/"},
    {"name": "Yann LeCun (Meta AI)",     "type": "rss",    "url": "https://ai.meta.com/blog/rss/"},
    {"name": "Demis Hassabis (DeepMind)","type": "rss",    "url": "https://deepmind.google/blog/rss.xml"},

    # --- COMPANY BLOGS ---
    {"name": "Anthropic",               "type": "rss",    "url": "https://www.anthropic.com/news/rss.xml"},
    {"name": "GitHub Blog (AI)",         "type": "rss",    "url": "https://github.blog/feed/"},
    {"name": "GitHub Copilot Changelog", "type": "rss",    "url": "https://github.blog/changelog/feed/"},
    {"name": "VS Code",                  "type": "rss",    "url": "https://code.visualstudio.com/feed.xml"},
    {"name": "Cognition (Devin)",        "type": "scrape", "url": "https://cognition.ai/blog"},
    {"name": "OpenAI",                   "type": "rss",    "url": "https://openai.com/news/rss.xml"},
    {"name": "Google DeepMind",          "type": "rss",    "url": "https://deepmind.google/blog/rss.xml"},
    {"name": "Microsoft AI",             "type": "rss",    "url": "https://blogs.microsoft.com/ai/feed/"},
    {"name": "Hugging Face",             "type": "rss",    "url": "https://huggingface.co/blog/feed.xml"},
    {"name": "Salesforce AI",            "type": "rss",    "url": "https://www.salesforce.com/blog/category/ai/feed/"},
    {"name": "ServiceNow AI",            "type": "rss",    "url": "https://www.servicenow.com/blogs/feed"},
    {"name": "Meta AI",                  "type": "rss",    "url": "https://ai.meta.com/blog/rss/"},

    # --- AI-FIRST IDEs & DEV TOOLS ---
    {"name": "Cursor",                   "type": "scrape", "url": "https://www.cursor.com/blog"},
    {"name": "Windsurf (Codeium)",       "type": "rss",    "url": "https://codeium.com/blog/rss.xml"},
    {"name": "Replit",                   "type": "rss",    "url": "https://blog.replit.com/rss.xml"},
    {"name": "Thinking Machines (Murati)","type": "scrape","url": "https://www.thinkingmachines.ai/blog"},

    # --- AGGREGATORS & NEWSLETTERS ---
    {"name": "Hacker News AI (API)",     "type": "api",    "url": "https://hn.algolia.com/api/v1/search?tags=story&query=AI+enterprise&hitsPerPage=5"},
    {"name": "Import AI (Jack Clark)",   "type": "rss",    "url": "https://jack-clark.net/feed/"},
    {"name": "Latent Space",             "type": "rss",    "url": "https://www.latent.space/feed"},
    {"name": "TLDR AI",                  "type": "rss",    "url": "https://tldr.tech/ai/rss"},
    {"name": "Lex Fridman Podcast",      "type": "rss",    "url": "https://lexfridman.com/feed/podcast/"},

    # --- DEV BLOGGERS ---
    {"name": "Simon Willison",           "type": "rss",    "url": "https://simonwillison.net/atom/everything/"},
    {"name": "KDNuggets",                "type": "rss",    "url": "https://www.kdnuggets.com/feed"},
    {"name": "Towards Data Science",     "type": "rss",    "url": "https://towardsdatascience.com/feed"},

    # --- ENTERPRISE AI ---
    {"name": "xAI Blog",                 "type": "scrape", "url": "https://x.ai/blog"},
    {"name": "SAP AI",                   "type": "rss",    "url": "https://www.sap.com/blogs/topics/sap-business-ai.rss"},
    {"name": "LangChain",                "type": "rss",    "url": "https://blog.langchain.dev/rss/"},
    {"name": "NVIDIA AI Blog",           "type": "rss",    "url": "https://blogs.nvidia.com/feed/"},
    {"name": "AWS Machine Learning",     "type": "rss",    "url": "https://aws.amazon.com/blogs/machine-learning/feed/"},
    {"name": "Azure AI",                 "type": "rss",    "url": "https://techcommunity.microsoft.com/t5/ai-azure-ai-services-blog/bg-p/Azure-AI-Services-Blog/feed"},
    {"name": "Mistral AI",               "type": "rss",    "url": "https://mistral.ai/news/rss.xml"},
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; NewsletterBot/1.0; +https://github.com)"
}

def check_rss(name, url):
    try:
        start = time.time()
        feed = feedparser.parse(url)
        elapsed = round(time.time() - start, 2)

        if feed.bozo and not feed.entries:
            return {"status": "DEAD", "reason": str(feed.bozo_exception)[:80], "items": 0, "elapsed": elapsed}

        count = len(feed.entries)
        if count == 0:
            return {"status": "EMPTY", "reason": "Feed parsed but no entries", "items": 0, "elapsed": elapsed}

        latest = feed.entries[0]
        title = latest.get("title", "no title")[:60]
        link  = latest.get("link", "no link")

        return {
            "status": "OK",
            "items": count,
            "elapsed": elapsed,
            "latest_title": title,
            "latest_link": link,
        }
    except Exception as e:
        return {"status": "ERROR", "reason": str(e)[:80], "items": 0, "elapsed": 0}


def check_scrape(name, url):
    try:
        start = time.time()
        r = httpx.get(url, headers=HEADERS, timeout=15, follow_redirects=True)
        elapsed = round(time.time() - start, 2)
        return {
            "status": "OK" if r.status_code == 200 else "DEAD",
            "http_status": r.status_code,
            "elapsed": elapsed,
            "note": "scrape target — needs scraper implementation",
            "content_length": len(r.text),
        }
    except Exception as e:
        return {"status": "ERROR", "reason": str(e)[:80], "elapsed": 0}


def check_api(name, url):
    try:
        start = time.time()
        r = httpx.get(url, headers=HEADERS, timeout=15)
        elapsed = round(time.time() - start, 2)
        data = r.json()
        hits = data.get("hits", [])
        return {
            "status": "OK" if r.status_code == 200 else "DEAD",
            "http_status": r.status_code,
            "items": len(hits),
            "elapsed": elapsed,
            "latest_title": hits[0]["title"][:60] if hits else "none",
        }
    except Exception as e:
        return {"status": "ERROR", "reason": str(e)[:80], "elapsed": 0}


def main():
    results = []
    print(f"\nAI Newsletter Source Validator")
    print(f"Run at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Testing {len(SOURCES)} sources...\n")
    print(f"{'Source':<35} {'Type':<8} {'Status':<8} {'Items':<6} {'Time':>6}s  Details")
    print("-" * 100)

    ok = dead = error = scrape = 0

    for s in SOURCES:
        name = s["name"]
        stype = s["type"]
        url = s["url"]

        if stype == "rss":
            r = check_rss(name, url)
        elif stype == "scrape":
            r = check_scrape(name, url)
        elif stype == "api":
            r = check_api(name, url)
        else:
            r = {"status": "SKIP", "reason": "unknown type"}

        r["name"] = name
        r["type"] = stype
        r["url"] = url
        results.append(r)

        status = r["status"]
        items  = r.get("items", "-")
        elapsed = r.get("elapsed", 0)
        detail = r.get("latest_title") or r.get("reason") or r.get("note") or ""

        if status == "OK":
            ok += 1
            marker = "[OK]  "
        elif stype == "scrape":
            scrape += 1
            marker = "[SCRP]"
        elif status in ("DEAD", "EMPTY"):
            dead += 1
            marker = "[DEAD]"
        else:
            error += 1
            marker = "[ERR] "

        print(f"{marker} {name:<33} {stype:<8} {status:<8} {str(items):<6} {elapsed:>6}s  {detail}")

    print("-" * 100)
    print(f"\nSummary: {ok} OK | {dead} Dead/Empty | {error} Errors | {scrape} Scrape-only")

    # Save results
    with open("feed_test_results.json", "w") as f:
        json.dump({"run_at": str(datetime.now()), "results": results}, f, indent=2)
    print(f"\nFull results saved to: feed_test_results.json")

    # Print dead/error feeds for action
    dead_feeds = [r for r in results if r["status"] not in ("OK",) and r["type"] == "rss"]
    if dead_feeds:
        print("\nFeeds needing attention (RSS only):")
        for r in dead_feeds:
            print(f"  - {r['name']}: {r['status']} — {r.get('reason', r.get('http_status', ''))}")

if __name__ == "__main__":
    main()

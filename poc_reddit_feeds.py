"""
POC: Validate Reddit RSS feeds and find best subreddits for AI newsletter
"""

import feedparser
import time

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; NewsletterBot/1.0)"}

CANDIDATES = [
    # Confirmed keeps
    {"sub": "AINews",            "reason": "Curated AI news, high signal"},
    {"sub": "promptengineering", "reason": "Enterprise prompt engineering, dev-focused"},

    # Other candidates to evaluate
    {"sub": "ChatGPT",           "reason": "OpenAI/ChatGPT enterprise use cases"},
    {"sub": "OpenAI",            "reason": "OpenAI announcements and discussion"},
    {"sub": "ClaudeAI",          "reason": "Anthropic/Claude news and use cases"},
    {"sub": "github",            "reason": "GitHub Copilot and AI dev tools"},
    {"sub": "devops",            "reason": "AI in CI/CD, infra, software delivery"},
    {"sub": "softwareengineering","reason": "AI impact on software engineers"},
    {"sub": "datascience",       "reason": "Applied AI and enterprise data"},
    {"sub": "LLMDevs",           "reason": "LLM development, enterprise apps"},
    {"sub": "Anthropic",         "reason": "Anthropic company news"},
    {"sub": "agi",               "reason": "AGI news and human impact"},
    {"sub": "technology",        "reason": "Broad tech/AI news"},
]

print("\nReddit Subreddit Validator")
print(f"Testing {len(CANDIDATES)} subreddits...\n")
print(f"{'Subreddit':<25} {'Status':<8} {'Members':<12} {'Items':<6} {'Latest Post'}")
print("-" * 100)

results = []

for c in CANDIDATES:
    sub = c["sub"]
    url = f"https://www.reddit.com/r/{sub}/top/.rss?t=week"

    try:
        start = time.time()
        feed = feedparser.parse(url)
        elapsed = round(time.time() - start, 2)

        if feed.bozo and not feed.entries:
            print(f"  [DEAD]  r/{sub:<22} — parse error")
            results.append({**c, "status": "dead"})
            continue

        count = len(feed.entries)
        if count == 0:
            print(f"  [EMPTY] r/{sub:<22} — no posts this week")
            results.append({**c, "status": "empty"})
            continue

        # Get subscriber count from feed metadata if available
        members = feed.feed.get("community_details_subscribers", "?")
        latest = feed.entries[0].get("title", "")[:55]

        print(f"  [OK]    r/{sub:<22} {str(members):<12} {count:<6} {latest}")
        results.append({**c, "status": "ok", "items": count, "members": members, "latest": latest})

    except Exception as e:
        print(f"  [ERR]   r/{sub:<22} — {str(e)[:50]}")
        results.append({**c, "status": "error"})

    time.sleep(0.5)  # be polite to Reddit

print("\n" + "=" * 100)
print("\nRECOMMENDED SUBREDDITS:")
print("-" * 100)
for r in results:
    if r["status"] == "ok":
        print(f"  r/{r['sub']:<25} — {r['reason']}")

print("\nSKIP:")
for r in results:
    if r["status"] != "ok":
        print(f"  r/{r['sub']:<25} — {r['status']}")

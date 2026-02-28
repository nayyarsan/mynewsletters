# Telegram Output Improvements — Design

**Date:** 2026-02-28
**Scope:** Fix missing summaries + improve Telegram digest format

---

## Problem

The GitHub Actions digest delivered to Telegram had three issues:

1. **Missing summaries** — The 6-dimension LLM analysis (What happened, Enterprise impact, etc.) did not appear in the Top 3 stories. `summarize.py` was summarizing every story in every category, exhausting the 50 req/day `claude-sonnet-4-6` quota and failing silently. `story.summary` remained `None`.
2. **Duplicate stories** — Top 3 stories appeared again in their category sections below.
3. **Empty categories** — Categories with no stories rendered a "No significant stories this week." placeholder, making the digest look sparse.
4. **Plain text only** — No use of Telegram's native HTML formatting; hard to scan on mobile.

---

## Approved Design

### Fix 1 — Summarize only top 3 (`summarize.py`)

Remove the loop that summarizes all category stories. Only the top 3 stories get the full 6-dimension analysis. Category list items (brief format) will show title + URL only — no snippet. This stays well within the 50 req/day limit (3 calls vs potentially 20+).

### Fix 2 — Telegram HTML formatting (`deliver.py`)

Switch `send_to_telegram` to use `parse_mode="HTML"`. Update all format functions:

- `<b>bold</b>` for section headers and story titles
- `<i>italic</i>` for source/category metadata lines
- `<a href="url">text</a>` for linked story titles in brief sections
- Unicode `────` rule as section divider (replaces `____`)
- `🔗` prefix on "Read more" links in full story format

### Fix 3 — Deduplicate category sections (`deliver.py`)

Before rendering each category section, exclude any story whose `canonical_url` is already in the Top 3. Pass the set of top-3 URLs into `format_digest`.

### Fix 4 — Hide empty categories (`deliver.py`)

Only render a category block if it has at least one story remaining after deduplication.

---

## Target Output Shape

```
<b>AI DIGEST</b> | Week of Feb 28, 2026

<b>TOP 3 MUST-READS</b>

<b>1. A Unified Experience for all Coding Agents</b>
<i>VS Code · Enterprise Software Delivery</i>

What happened: ...
Enterprise impact: ...
For developers: ...
How to use it: ...

🔗 Read more: https://code.visualstudio.com/...

────────────────────────────────
<b>ENTERPRISE SOFTWARE DELIVERY</b>

• <a href="...">safe-py-runner: Secure & lightweight Python execution</a>
• <a href="...">Introducing GitHub Copilot for Azure</a>

────────────────────────────────
<b>GENERAL SIGNIFICANCE</b>

• <a href="...">Google API Keys Weren't Secrets...</a>
```

---

## Files Changed

| File | Change |
|------|--------|
| `pipeline/summarize.py` | Remove category-level summarize loop; only top 3 |
| `pipeline/deliver.py` | HTML parse mode, dedup, hide empty cats, new format functions |

---

## Out of Scope

- Changing ranking logic
- Adding new categories
- Changing the summarize prompt or dimensions

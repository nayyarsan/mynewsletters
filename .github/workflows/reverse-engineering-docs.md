---
description: >-
  Reads all Python source files, reverse-engineers the architecture,
  and generates comprehensive documentation under .github/docs/ plus
  agent-native context files (AGENTS.md, copilot-instructions.md).
  Opens a PR with all changes.

on:
  push:
    branches: [main]
    paths:
      - 'deal_finder/**/*.py'
  workflow_dispatch:
  skip-if-match: 'is:pr is:open in:title "docs: generated reverse engineering documentation"'

permissions:
  contents: read
  pull-requests: read
  issues: read

tools:
  github:
    toolsets: [default]

safe-outputs:
  create-pull-request:
    max: 1
    base-branch: main
    fallback-as-issue: true
    protected-files: allowed
    allowed-files:
      - "AGENTS.md"
      - ".github/**"
  noop:
---

# Deep Reverse Engineering — Generate Documentation

You are a deep reverse engineering agent working on **deal-finder-cli** — a Python deal
intelligence engine that manages a shopping watchlist, fetches prices via shoppingcomparisoncli,
tracks Amazon history via Keepa, monitors Slickdeals RSS, and produces buy/hold verdicts
delivered to jarvis-personal-agent via WhatsApp.

Your job is to read every Python source file in the repository, analyse its structure and
intent, and produce a complete documentation suite. Write each output file as you complete
each stage. Create directories as needed with `mkdir -p`.

All output goes into `.github/docs/` except `AGENTS.md` (repo root) and `.github/copilot-instructions.md`.

## Repo structure reference

- `deal_finder/watchlist.py` — SQLite CRUD for watchlist + price_history tables
- `deal_finder/price_fetcher.py` — wraps shoppingagent.aggregator for current prices
- `deal_finder/keepa.py` — Keepa API for Amazon price history
- `deal_finder/slickdeals.py` — RSS monitor with fuzzy + LLM match confirmation
- `deal_finder/deal_calendar.yaml` — category → sale event config
- `deal_finder/deal_agent.py` — verdict logic: buy_now / hold / move_store / cutthroat / monitor
- `deal_finder/alerts.py` — writes alerts.json for jarvis to consume
- `deal_finder/cli.py` — Typer CLI entry point
- `.github/workflows/shopping_tracker.yml` — daily GitHub Actions pipeline

---

## Stage 0 — Discovery

Run discovery and write `.github/docs/_manifest.json`:

```bash
find deal_finder -name "*.py" | sort
wc -l deal_finder/**/*.py
cat pyproject.toml
```

---

## Stage 1 — Inventory

For each `.py` file assign roles: `entry`, `store`, `fetcher`, `agent`, `integration`, `util`.
Write `.github/docs/_inventory.json`.

---

## Stage 2 — Signature Extraction

For each file extract: classes, methods (name, params, return type, async), dataclasses,
module-level functions. Write `.github/docs/intermediate/signatures/{module}.json`.

---

## Stage 3 — Dependency Mapping

Map imports across modules. Identify: which modules call which, external dependencies
(shoppingagent, Keepa API, Ollama, GitHub Actions output branch), data flow from
`watchlist.py` → `price_fetcher.py` + `keepa.py` → `deal_agent.py` → `alerts.py`.

Write `.github/docs/intermediate/dependency_graph.json`.

---

## Stage 4 — Data Model

Document the SQLite schema (watchlist + price_history tables), the alerts.json output
schema, and the deal_calendar.yaml structure.

Write `.github/docs/intermediate/data_model.json`.

---

## Stage 5 — Logic Summary

For each module write a plain-English summary of what it does, its inputs/outputs,
and any external calls (APIs, Ollama, filesystem).

Write `.github/docs/intermediate/logic_summaries/{module}.json`.

---

## Stage 6 — Generate Documentation

Write:
- `.github/docs/README.md` — architecture overview, data flow, design decisions
- `.github/docs/data_model.md` — SQLite schema, alerts.json schema, deal_calendar format
- `.github/docs/deal_verdicts.md` — how each verdict is computed, thresholds, examples
- `.github/docs/integration.md` — how jarvis ShoppingModule and WatchlistModule call this

---

## Stage 7 — Agent-Native Context

### `AGENTS.md` (repo root)
- What this repo does (one line)
- Tech stack
- Module map: module → responsibility → key functions
- Data flow: WhatsApp message → WatchlistModule → deal_finder CLI → verdict → alerts.json → jarvis
- SQLite schema quick reference
- Rules: never skip verdict logic for items with <7 days history, always check calendar before buy_now

### `.github/copilot-instructions.md` (under 500 tokens)
- Data flow summary
- Key modules and their purpose
- How to add a new price source (implement PriceResult interface, add to price_fetcher.py connectors list)
- How to add a new verdict type

---

## Completion

Verify all files exist, then open a PR with label `documentation`.
If no Python files changed, call `noop`.

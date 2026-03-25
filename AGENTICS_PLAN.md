# Agentics Plan — mynewsletters

Add [GitHub Agentic Workflows](https://github.com/githubnext/agentics) to strengthen the automated newsletter pipeline.

## Prerequisites

```bash
gh extension install github/gh-aw
```

## Workflows to Add

- [ ] **CI Doctor** — monitors `newsletter.yml` GitHub Action; surfaces failures before Telegram delivery breaks
  ```bash
  gh aw add ci-doctor
  ```

- [ ] **Tech Content Editorial Board** — daily review of generated newsletter content for technical rigor
  ```bash
  gh aw add tech-content-editorial-board
  ```

- [ ] **Link Checker** — finds and fixes broken source URLs in the 35-feed list automatically
  ```bash
  gh aw add link-checker
  ```

- [ ] **Weekly Research** — augments the pipeline with structured research inputs (arXiv + curated sources)
  ```bash
  gh aw add weekly-research
  ```

- [ ] **Daily Malicious Code Scan** — watches for compromised RSS/scraping sources being injected
  ```bash
  gh aw add daily-malicious-code-scan
  ```

- [ ] **Autoloop** — iteratively optimises ranking heuristics against a quality metric you define
  ```bash
  gh aw add autoloop
  ```

- [ ] **Issue Triage** — auto-labels incoming issues and PRs
  ```bash
  gh aw add issue-triage
  ```

- [ ] **Plan** (`/plan` command) — breaks big issues into tracked sub-tasks
  ```bash
  gh aw add plan
  ```

## Keep Workflows Updated

```bash
gh aw upgrade
gh aw update
```

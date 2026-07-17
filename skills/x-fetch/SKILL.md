---
name: x-fetch
description: Use when Codex needs to track one or more X/Twitter creators within a recent time window, extract recent posts quickly, classify them by asset class, and summarize them in a timeline-first format with minimal token usage.
---

# X Fetch

## Overview

Pull recent X posts fast, then summarize them with deterministic scripts before spending tokens on narrative synthesis. Use this for daily creator tracking, recent-window scans, and repeated monitoring tasks where time accuracy and low-token output matter more than elaborate prose.

## Workflow

1. Run `scripts/fetch_x_posts.py` to fetch and normalize posts for one or more users.
2. Run `scripts/summarize_posts.py` on the JSON output.
3. Default to `timeline` mode. Use `grouped` or `card` only when the user asks for a different format.
4. Only add extra written interpretation after the scripts finish and the user actually needs it.

## Quick Start

### Single user, recent 3 days

```powershell
& 'C:\Users\jiuxi\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' `
  'C:\Users\jiuxi\Documents\自动抓取油管kol信息\skills\x-fetch\scripts\fetch_x_posts.py' `
  --users chenreason --days 3 --limit 40 `
  --output 'C:\Users\jiuxi\Documents\自动抓取油管kol信息\skills\x-fetch\outputs\chenreason-3d.json'

& 'C:\Users\jiuxi\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' `
  'C:\Users\jiuxi\Documents\自动抓取油管kol信息\skills\x-fetch\scripts\summarize_posts.py' `
  --input 'C:\Users\jiuxi\Documents\自动抓取油管kol信息\skills\x-fetch\outputs\chenreason-3d.json' `
  --mode timeline
```

### Multiple users from targets file

```powershell
& 'C:\Users\jiuxi\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' `
  'C:\Users\jiuxi\Documents\自动抓取油管kol信息\skills\x-fetch\scripts\fetch_x_posts.py' `
  --targets 'C:\Users\jiuxi\Documents\自动抓取油管kol信息\skills\x-fetch\targets\sample_targets.json' `
  --days 1 --limit 30 `
  --output 'C:\Users\jiuxi\Documents\自动抓取油管kol信息\skills\x-fetch\outputs\daily.json'
```

### Daily batch in one command

```powershell
& 'C:\Users\jiuxi\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' `
  'C:\Users\jiuxi\Documents\自动抓取油管kol信息\skills\x-fetch\scripts\run_daily_batch.py' `
  --targets 'C:\Users\jiuxi\Documents\自动抓取油管kol信息\skills\x-fetch\targets\sample_targets.json' `
  --days 1 --limit 30 `
  --state-file 'C:\Users\jiuxi\Documents\自动抓取油管kol信息\skills\x-fetch\state\daily-state.json' `
  --output-dir 'C:\Users\jiuxi\Documents\自动抓取油管kol信息\skills\x-fetch\outputs'
```

## Output Rules

- Default output mode is `timeline`.
- Sort by parsed publish time descending.
- Classify each post into one asset class only: `crypto`, `us-stocks`, `a-shares`, `macro`, `ai`, `other`.
- Keep one-line summaries compact. Do not expand every post unless the user asks.
- Keep original URL and raw text in JSON so later summaries can be re-rendered without refetching.
- For recurring daily runs, use `run_daily_batch.py` with `--state-file` so only unseen posts are emitted.

See `references/output-contract.md` for exact JSON and Markdown shapes.

## Resource Guide

### scripts/

- `common.py`: shared parsing, classification, filtering, and rendering helpers
- `fetch_x_posts.py`: fetch + normalize + window filter
- `summarize_posts.py`: render timeline, grouped, or card summaries
- `run_daily_batch.py`: one-shot daily fetch + timeline output for a targets file

### references/

- `classification-rules.md`: keyword-based asset class rules
- `output-contract.md`: compact JSON and Markdown output formats

### targets/

Store creator lists here as JSON. Keep this separate from scripts so target sets can be swapped without code edits.

Supported target fields:

- top-level `limit_per_user`
- top-level `default_window.days`
- top-level `include_replies`
- per-user object:
  - `username`
  - `include_replies`

## Practical Notes

- Prefer the script outputs over ad hoc browsing when the task is recurring or window-based.
- If exact timestamps cannot be parsed, keep the raw time text and mark the entry as uncertain instead of guessing.
- If fetch quality is poor for a creator, swap the underlying source later. The reporting layer should stay unchanged.

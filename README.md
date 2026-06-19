# Jobs Auto Scanner — Scan-Only

Autonomous job scanner: scrape job boards, score each posting against your candidate
profile with a local LLM, and keep the suitable ones in a searchable dashboard.

> **This is the `scan-only` branch.** Resume tailoring, cover-letter generation, and
> auto-email have been removed. The scanner scrapes and scores; you review matches in
> the dashboard and apply yourself. For the full generate-and-email pipeline, see the
> `main` branch.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        Job Sources                              │
│  Greenhouse · Lever · Ashby · Workable · RemoteOK · Remotive    │
│  Jobicy · HN Who's Hiring · SimplifyJobs                        │
└────────────────────────────┬────────────────────────────────────┘
                             │  1000+ jobs/cycle
                             v
                    ┌─────────────────┐
                    │  Job Scanner    │  httpx async scraper
                    │  + Scorer       │  LLM fit score (0–100)
                    └────────┬────────┘
                             │  jobs scoring >= MIN_SCORE_SAVE
                             v
                    ┌─────────────────┐
                    │  SQLite Store   │  dedup, status tracking
                    └────────┬────────┘
                             │
                             v
                    ┌─────────────────┐
                    │  Web Dashboard  │  localhost:8765
                    │  (review matches│  start/stop scanner,
                    │   + mark applied)│  mark jobs applied
                    └─────────────────┘
```

---

## Features

- Scrapes 1000+ job postings per cycle across 9 sources (Greenhouse, Lever, Ashby, Workable, RemoteOK, Remotive, Jobicy, HN Who's Hiring, SimplifyJobs)
- Scores each job against your candidate profile using a local LLM (Gemma via LM Studio by default)
- Keeps qualifying jobs (score ≥ `MIN_SCORE_SAVE`) in a SQLite store with dedup and status tracking
- Flags strong matches (score ≥ `MIN_SCORE_GOOD`) for quick triage
- Web dashboard at `localhost:8765` to review matches, start/stop the scanner, and mark jobs as applied
- Daemon mode: continuous scan loop on a configurable interval
- Bring your own LLM — any OpenAI-compatible server works (LM Studio, Ollama, vLLM, etc.)

---

## Prerequisites

| Requirement | Notes |
|---|---|
| Python 3.12+ | |
| [uv](https://docs.astral.sh/uv/) | dependency manager |
| LM Studio (or Ollama) | running a model on a local OpenAI-compatible endpoint |

---

## Quick Start

```bash
# 1. Configure the LLM endpoint
cp .env.example .env
# Edit .env — set LLM_BASE_URL and LLM_MODEL

# 2. Install dependencies
uv sync

# 3. Launch the dashboard
uv run python main.py dashboard
```

Open `http://localhost:8765` in your browser.

---

## Configuration

### .env

```ini
LLM_BASE_URL=http://localhost:1234/v1   # LM Studio / Ollama endpoint
LLM_MODEL=google/gemma-4-26b-a4b        # model name as shown in LM Studio
```

### config.py

| Parameter | Default | Description |
|---|---|---|
| `SCAN_INTERVAL_SECONDS` | `1200` | Seconds between daemon scans (20 min) |
| `DEFAULT_ROLES` | `["Software Engineer", "ML Engineer", "Backend Engineer"]` | Roles searched when none are specified |
| `REMOTE_ONLY` | `True` | Filter to remote positions only |
| `MIN_SCORE_SAVE` | `45` | Jobs below this score are discarded immediately |
| `MIN_SCORE_GOOD` | `70` | Jobs at/above this are flagged as strong matches |

---

## How It Works

### 1. Scraping

`job_scanner/scanner.py` fans out async HTTP requests across all configured sources. Each source adapter normalises raw listings into a common schema (title, company, URL, description). Duplicate jobs are fingerprinted by URL and skipped.

### 2. Scoring

Each fresh, high-score posting is sent to the local LLM for a fit check (`job_scanner/quality.py`) that rejects role/seniority mismatches. Jobs below `MIN_SCORE_SAVE` are dropped; the rest are saved to the store.

### 3. Review

Saved jobs surface in the dashboard, sorted by status (new / applied / skipped) with their LLM score and rationale. Open the posting via the **Apply** link and mark it applied when done.

---

## Dashboard

Open `http://localhost:8765` after running `uv run python main.py dashboard`.

Key features:
- Live job feed with LLM scores and rationale
- Scanner start/stop control
- Status management: mark jobs as `applied`
- Source breakdown and live stat cards

---

## Commands Reference

```bash
# Run a one-off scan (optional: specify roles and filters)
uv run python main.py scan
uv run python main.py scan --roles "ML Engineer" "Backend SWE"
uv run python main.py scan --roles "Software Engineer" --no-remote
uv run python main.py scan --min-score 60 --no-hn --no-aggregators

# List saved jobs
uv run python main.py list
uv run python main.py list --status new

# Start the web dashboard (default port 8765)
uv run python main.py dashboard
uv run python main.py dashboard --port 9000

# Run the continuous daemon (scan loop)
uv run python main.py daemon
```

---

## Notes

**Bring your own LLM.** Any OpenAI-compatible server works — LM Studio, Ollama, vLLM, a remote API, etc. Set `LLM_BASE_URL` and `LLM_MODEL` in `.env`.
</content>
</invoke>

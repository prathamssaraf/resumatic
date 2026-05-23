# Resumatic

Fully autonomous job application pipeline: scrape, score, generate, and email tailored resumes on autopilot.

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
                             │  top jobs (score >= threshold)
                             v
                    ┌─────────────────┐
                    │  SQLite Store   │  dedup, status tracking
                    └────────┬────────┘
                             │
                             v
                    ┌─────────────────────────────────┐
                    │       Resume Builder            │
                    │                                 │
                    │  Kuzu Graph  ──► LLM prompt     │
                    │  (profile,       (tailored      │
                    │   metrics,        bullets)      │
                    │   projects)                     │
                    │           │                     │
                    │           v                     │
                    │      XeLaTeX compile            │
                    │      page-count check           │
                    │      LLM compression fallback   │
                    └────────┬────────────────────────┘
                             │  1-page PDF + cover letter
                             v
                    ┌─────────────────┐
                    │  Gmail Notifier │  SMTP App Password
                    └────────┬────────┘
                             │
                             v
                    ┌─────────────────┐
                    │  Web Dashboard  │  localhost:8765
                    │  (monitoring +  │  manual queue
                    │   manual apply) │
                    └─────────────────┘
```

---

## Features

- Scrapes 1000+ job postings per cycle across 9 sources (Greenhouse, Lever, Ashby, Workable, RemoteOK, Remotive, Jobicy, HN Who's Hiring, SimplifyJobs)
- Scores each job against your candidate profile using a local LLM (Gemma 4 26B via LM Studio by default)
- Generates tailored 1-page LaTeX resumes compiled with XeLaTeX (Carlito font)
- Generates matching cover letters per application
- Enforces strict 1-page layout: 137-character bullet targets, 3 projects, 3 bullets per experience section, post-compile page checker with LLM compression fallback
- Emails the best matches automatically via Gmail SMTP
- Candidate profile stored in a Kuzu knowledge graph: projects, skills, work experience, and immutable metrics
- Web dashboard at `localhost:8765` for monitoring pipeline status, reviewing jobs, and manually queuing applications
- Daemon mode: continuous scan + auto-email loop on a configurable interval
- Bring your own LLM — any OpenAI-compatible server works (LM Studio, Ollama, vLLM, etc.)

---

## Prerequisites

| Requirement | Notes |
|---|---|
| Python 3.12+ | |
| [uv](https://docs.astral.sh/uv/) | dependency manager |
| XeLaTeX | `texlive-xetex` on Linux, MacTeX on macOS |
| Carlito font | included in most TeX distributions; install separately if missing |
| LM Studio (or Ollama) | running a 26B+ parameter model on a local OpenAI-compatible endpoint |
| Gmail App Password | required for auto-email; [generate one here](https://myaccount.google.com/security) |

---

## Quick Start

```bash
# 1. Clone
git clone https://github.com/youruser/resumatic.git
cd resumatic

# 2. Configure credentials
cp .env.example .env
# Edit .env — set GMAIL_SENDER, GMAIL_APP_PASSWORD, GMAIL_RECIPIENT, LLM_BASE_URL

# 3. Fill in your profile
cp graph/seed_data.example.py graph/seed_data.py
# Edit graph/seed_data.py — replace placeholder data with your own

# 4. Install dependencies
uv sync

# 5. Seed the knowledge graph and launch the dashboard
uv run python main.py seed
uv run python main.py dashboard
```

Open `http://localhost:8765` in your browser.

---

## Configuration

### .env

```ini
GMAIL_SENDER=you@gmail.com
GMAIL_APP_PASSWORD=xxxx-xxxx-xxxx-xxxx
GMAIL_RECIPIENT=you@gmail.com          # where job alerts are sent
LLM_BASE_URL=http://localhost:1234/v1  # LM Studio / Ollama endpoint
LLM_MODEL=gemma-3-27b-it              # model name as shown in LM Studio
```

### config.py

Tunable parameters in `config.py`:

| Parameter | Default | Description |
|---|---|---|
| `SCAN_INTERVAL_SECONDS` | `1200` | Seconds between daemon scans (20 min) |
| `MIN_SCORE_TO_EMAIL` | `70` | Minimum LLM fit score to trigger auto-email |
| `MAX_EMAILS_PER_SCAN` | `3` | Max emails sent per scan cycle |
| `DB_KEEP_TOP` | `5` | Jobs retained in the store per cycle |
| `DEFAULT_ROLES` | `["Software Engineer", "ML Engineer", "Backend Engineer"]` | Roles searched when none are specified |
| `REMOTE_ONLY` | `True` | Filter to remote positions only |
| `MIN_SCORE_SAVE` | `45` | Jobs below this score are discarded immediately |

---

## How It Works

### 1. Scraping

`job_scanner/scanner.py` fans out async HTTP requests across all configured sources. Each source adapter normalises raw listings into a common schema (title, company, URL, description). Duplicate jobs are fingerprinted by URL and skipped.

### 2. Scoring

Each job description is sent to the local LLM alongside a compact summary of your profile extracted from the Kuzu graph. The model returns a numeric fit score (0–100) and a short rationale. Jobs below `MIN_SCORE_SAVE` are dropped; those above `MIN_SCORE_TO_EMAIL` are queued for resume generation.

### 3. Knowledge Graph

`graph/seed_data.py` is the single source of truth for your profile. On `uv run python main.py seed`, this data is loaded into a Kuzu embedded graph database. The resume builder queries the graph at generation time to pull the most relevant projects, skills, and metrics for a given job description.

### 4. Resume Generation

`resume_builder/pipeline.py` orchestrates:

1. Graph query — fetch candidate profile nodes relevant to the target JD
2. LLM call — generate tailored bullet points within character limits
3. LaTeX render — inject bullets into the `.tex` template
4. XeLaTeX compile — produce a PDF
5. Page-count check — if the PDF exceeds one page, the LLM compresses the longest bullets and recompiles
6. Cover letter — separate LLM call produces a matching cover letter

### 5. Notification

`notifier.py` sends the PDF and cover letter as email attachments via Gmail SMTP using an App Password. No OAuth required.

---

## Dashboard

Open `http://localhost:8765` after running `uv run python main.py dashboard`.

Key features:
- Live job feed with LLM scores and rationale
- Status management: mark jobs as `new`, `applied`, or `skip`
- Manual apply button: runs the full resume pipeline for any saved job
- Pipeline log viewer
- Daemon status indicator (running / stopped)

---

## Commands Reference

```bash
# Seed / re-seed the knowledge graph from seed_data.py
uv run python main.py seed

# Run a one-off scan (optional: specify roles and filters)
uv run python main.py scan
uv run python main.py scan --roles "ML Engineer" "Backend SWE"
uv run python main.py scan --roles "Software Engineer" --no-remote
uv run python main.py scan --min-score 60 --no-hn --no-aggregators

# List saved jobs
uv run python main.py list
uv run python main.py list --status new

# Generate a resume for a specific saved job
uv run python main.py apply <job-id>
uv run python main.py apply <job-id> --no-cover

# Generate a resume from a local JD file
uv run python main.py resume --file path/to/jd.txt

# Start the web dashboard (default port 8765)
uv run python main.py dashboard
uv run python main.py dashboard --port 9000

# Run the continuous daemon (scan + email loop)
uv run python main.py daemon
```

---

## Notes

**Bring your own LLM.** Any OpenAI-compatible server works — LM Studio, Ollama, vLLM, a remote API, etc. Set `LLM_BASE_URL` and `LLM_MODEL` in `.env`. A 26B+ parameter model is recommended for resume quality; smaller models tend to produce over-length bullets that require more compression passes.

**Metrics are immutable.** Numbers in `METRICS` inside `seed_data.py` are treated as ground truth and are never rewritten by the LLM. The pipeline can select which metrics to surface but cannot alter their values.

**XeLaTeX must be on your PATH.** Run `xelatex --version` to confirm before starting.

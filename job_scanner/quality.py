"""
LLM-driven job screening.

Each job is checked against a list of criteria — one criterion per LLM call,
top-to-bottom, stopping at the first failure. A job that passes every criterion
is Approved and then given a 0-100 fit score. All judgement is done by the local
Gemma model via job_scanner.llm; there is no regex/keyword filtering.

To change what gets approved, edit CRITERIA (and CANDIDATE) below.
"""
from __future__ import annotations
import re
from .llm import call_json

# Candidate profile the screen is tuned to. Embedded in every prompt so the
# model judges fit against a concrete person rather than a generic standard.
CANDIDATE = (
    "The candidate is an early-career software engineer: MS in Computer Science, "
    "about 1-1.5 years of internship experience, strong in Python, ML / LLM / RAG, "
    "backend and full-stack web (FastAPI, React, Node, TypeScript), Docker, and AWS. "
    "They will need US work-visa sponsorship in the future and cannot take roles "
    "that require US citizenship or a security clearance."
)

# Ordered list of (key, question). A job must PASS every criterion to be Approved.
# Checked top-to-bottom, stopping at the first failure, so put the cheapest /
# most-common rejections first. Each question is answered yes/no by the model,
# where "yes" means the job satisfies the criterion. Edit freely.
CRITERIA: list[tuple[str, str]] = [
    ("legitimate",
     "Is this a legitimate, paid job posting (NOT unpaid, equity-only, "
     "commission-only, a course/bootcamp advertisement, or crypto/spam)?"),
    ("full_time",
     "Is this a full-time position (NOT an internship or co-op)?"),
    ("role_type",
     "Is this primarily a software, ML, backend, or full-stack ENGINEERING role "
     "(NOT sales, marketing, HR/recruiting, finance, legal, or IT helpdesk/support)?"),
    ("level",
     "Is this an early-career role appropriate for a new grad to mid-level engineer "
     "(roughly 0-2 years)? Answer no if it is senior, staff, principal, distinguished, "
     "lead, architect, manager, director, or VP level."),
    ("experience",
     "Does this role require 2 or fewer years of professional experience? "
     "Answer no if it asks for 3 or more years."),
    ("location",
     "Is this role based in the United States or fully US-remote? "
     "Answer no if it is based only in another country."),
    ("work_authorization",
     "Could a candidate who needs future US visa sponsorship take this role? "
     "Answer no ONLY if it explicitly requires US citizenship, an active security "
     "clearance, ITAR eligibility, or states that no sponsorship is available."),
]

_MAX_DESC = 100000  # effectively no cap — send the whole JD to the model


def _excerpt(desc: str) -> str:
    """
    Clean and cap the JD. Requirements (seniority, years of experience) almost
    always sit at the END of a posting, so for over-length JDs we keep both the
    head and the tail rather than truncating from the front — otherwise the
    screen never sees "7+ years" and wrongly approves senior roles.
    """
    clean = re.sub(r"<[^>]+>", " ", desc or "")
    clean = re.sub(r"\s+", " ", clean).strip()
    if len(clean) <= _MAX_DESC:
        return clean
    head = clean[: int(_MAX_DESC * 0.65)]
    tail = clean[-int(_MAX_DESC * 0.35):]
    return f"{head}\n…[middle trimmed]…\n{tail}"


def _job_block(title: str, location: str, desc: str) -> str:
    loc = location.strip() if location else "(not specified)"
    return (
        f"Job Title: {title}\n"
        f"Job Location (from the source listing): {loc}\n\n"
        f"Job Posting:\n{_excerpt(desc)}"
    )


def check_criterion(question: str, title: str, desc: str, location: str = "") -> tuple[bool, str]:
    """
    Ask Gemma a single yes/no criterion about one job. Returns (passed, reason).
    Raises on LLM failure — the caller skips the job this cycle and retries.
    """
    system = (
        "You screen job postings for a specific candidate.\n" + CANDIDATE +
        "\n\nYou are given ONE yes/no criterion. Judge it using the job posting "
        "and its listed location. 'pass' = true means the job SATISFIES the "
        "criterion. If the posting truly gives no relevant information, lean "
        "towards true. "
        'Respond with JSON only: {"pass": true|false, "reason": "<short phrase>"}.'
    )
    user = f"Criterion: {question}\n\n" + _job_block(title, location, desc)
    result = call_json(system, user, max_tokens=512, temperature=0.1)
    if not isinstance(result, dict):
        raise RuntimeError(f"check_criterion: expected dict, got {type(result).__name__}")
    return bool(result.get("pass", False)), str(result.get("reason", "")).strip()


def score_fit(title: str, desc: str, location: str = "") -> tuple[int, str]:
    """Ask Gemma to rate overall fit 0-100 for an already-approved job."""
    system = (
        "You rate how well a job fits a specific candidate.\n" + CANDIDATE +
        "\n\nReturn a 0-100 fit score (higher = stronger match to the candidate's "
        "skills and level) and a one-line reason. "
        'Respond with JSON only: {"score": <int 0-100>, "reason": "<short phrase>"}.'
    )
    user = _job_block(title, location, desc)
    result = call_json(system, user, max_tokens=512, temperature=0.2)
    if not isinstance(result, dict):
        raise RuntimeError(f"score_fit: expected dict, got {type(result).__name__}")
    try:
        score = int(result.get("score", 0))
    except (TypeError, ValueError):
        score = 0
    return max(0, min(100, score)), str(result.get("reason", "")).strip()


def evaluate_job(job: dict) -> dict:
    """
    Run a job through every criterion (one LLM call each, short-circuiting on the
    first failure), then score it if approved. Returns:
        {"approved": bool, "score": int, "reason": str, "failed": str | None}
    Raises on LLM failure (propagated so the scanner can skip + retry the job).
    """
    title    = job.get("title", "")
    desc     = job.get("description", "")
    location = job.get("location", "")
    for key, question in CRITERIA:
        passed, reason = check_criterion(question, title, desc, location)
        if not passed:
            return {
                "approved": False,
                "score": 0,
                "reason": f"{key}: {reason}" if reason else f"failed {key}",
                "failed": key,
            }
    score, reason = score_fit(title, desc, location)
    return {"approved": True, "score": score, "reason": reason, "failed": None}

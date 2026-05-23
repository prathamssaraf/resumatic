"""
Job quality scorer.

Logic:
  - Any US tech job that passes hard filters starts at 70
  - Skill match from Pratham's stack adds up to +30 on top
  - Hard rejects: no sponsorship, clearance, ITAR, internship, 3+ yrs exp, noise
"""
from __future__ import annotations
import re
from .sources.common import is_recent

# ── Hard reject patterns ───────────────────────────────────────────────────────
_NO_SPONSORSHIP = re.compile(
    r"no visa sponsorship|does not offer sponsorship|will not sponsor|"
    r"sponsorship not available|without sponsorship|"
    r"must be authorized|authorization to work|work authorization required|"
    r"us citizen(ship)? (is )?required|security clearance|clearance required|itar",
    re.I,
)

_INTERNSHIP = re.compile(r"\bintern(ship)?\b", re.I)

_HIGH_EXP = re.compile(
    r"\b([3-9]\d*|\d{2,})\+?\s*(?:to\s*\d+\s*)?years?\s+(?:of\s+)?(?:professional\s+)?experience\b"
    r"|\bminimum\s+[3-9]\d*\s+years?\b"
    r"|\b[3-9]\+\s*yrs?\b",
    re.I,
)

_NOISE = re.compile(
    r"\b(course|tutorial|newsletter|podcast|giveaway|airdrop|crypto|nft|web3|casino|gambling)\b",
    re.I,
)

_UNPAID = re.compile(
    r"\bunpaid\b|equity.only|commission.only|no budget|for exposure", re.I
)

# ── Pratham's stack — proficient skills worth more ────────────────────────────
_STACK_PROFICIENT = {
    "llm", "large language model", "rag", "retrieval augmented", "transformers",
    "prompt engineering", "pytorch", "machine learning", "deep learning",
    "computer vision", "yolo", "opencv", "cnn",
    "fastapi", "react", "node.js", "nodejs", "rest api", "restful",
    "full stack", "full-stack", "postgresql", "postgres", "firebase",
    "aws", "docker", "python", "typescript", "javascript", "java", "sql",
    "flutter", "tailwind",
}

_STACK_FAMILIAR = {
    "tensorflow", "langchain", "llamaindex", "cuda",
    "redis", "mysql", "kubernetes", "k8s", "ci/cd",
    "next.js", "nextjs", "django", "go", "golang", "rust",
    "microservices", "distributed systems", "data engineering",
    "mlops", "inference", "fine-tuning", "embedding",
}


def _recency_bonus(posted_date: str) -> int:
    from datetime import datetime, timezone
    if not posted_date:
        return 0
    try:
        dt = datetime.fromisoformat(posted_date.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        age = (datetime.now(tz=timezone.utc) - dt).days
        if age <= 1:  return 15
        if age <= 7:  return 8
        if age <= 14: return 3
    except Exception:
        pass
    return 0


def evaluate(job: dict, roles: list[str] = None, remote_only: bool = False) -> tuple[int, str]:
    title = (job.get("title") or "").lower()
    desc  = (job.get("description") or "").lower()
    text  = f"{title} {desc}"

    # ── Hard rejects ──────────────────────────────────────────────────────────
    if not job.get("url"):
        return 0, "no URL"
    if not is_recent(job.get("posted_date", "")):
        return 0, "stale posting"
    if _NOISE.search(text):
        return 0, "noise/spam"
    if _UNPAID.search(text):
        return 0, "unpaid/equity-only"
    if _NO_SPONSORSHIP.search(text):
        return 0, "no sponsorship"
    if job.get("sponsorship") in {"Does Not Offer Sponsorship", "U.S. Citizenship is Required"}:
        return 0, "no sponsorship"
    if _INTERNSHIP.search(title):
        return 0, "internship"
    if _HIGH_EXP.search(text):
        return 0, "requires 3+ years experience"

    # ── Base score: any tech job in US starts at 70 ───────────────────────────
    score = 70
    tags: list[str] = []

    # ── Skill match bonus (up to +30) ─────────────────────────────────────────
    prof_hits = [t for t in _STACK_PROFICIENT if t in text]
    fam_hits  = [t for t in _STACK_FAMILIAR  if t in text]

    skill_bonus = min(20, len(prof_hits) * 4) + min(10, len(fam_hits) * 2)
    score += skill_bonus

    if prof_hits:
        tags.append(f"stack:{','.join(prof_hits[:5])}")
    if fam_hits:
        tags.append(f"also:{','.join(fam_hits[:3])}")

    # ── Recency bonus ─────────────────────────────────────────────────────────
    score += _recency_bonus(job.get("posted_date", ""))

    final = min(100, score)
    return final, "; ".join(tags) if tags else "us tech job"


def filter_jobs(jobs: list[dict], roles: list[str] = None, remote_only: bool = False, min_score: int = 50) -> list[dict]:
    results = []
    for j in jobs:
        sc, reason = evaluate(j, roles, remote_only)
        if sc >= min_score:
            j["score"] = sc
            j["score_reason"] = reason
            results.append(j)
    results.sort(key=lambda x: (x.get("posted_date", ""), x["score"]), reverse=True)
    return results

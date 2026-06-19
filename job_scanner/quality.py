"""
Job quality scorer.

Logic:
  - Any US tech job that passes hard filters starts at 70
  - Skill match from Pratham's stack adds up to +30 on top
  - Hard rejects: no sponsorship, clearance, ITAR, internship, 3+ yrs exp,
                  senior/staff/principal/director/VP/EM titles,
                  wrong role type (sales/marketing/HR/finance/IT-ops/legal), noise
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

# Non-US locations — checked against the LOCATION field only.
# Denylist of foreign countries/cities so global ATS boards (Stripe Dublin,
# Cohere London, etc.) don't produce resumes for jobs the candidate can't take.
# Empty or generic "Remote" locations are kept (ambiguous — usually US/US-remote).
_NON_US_LOCATION = re.compile(
    r"\b(ireland|dublin|united kingdom|england|scotland|wales|london|manchester|"
    r"canada|canadian|british columbia|ontario|toronto|vancouver|montreal|"
    r"india|bengaluru|bangalore|gurugram|hyderabad|mumbai|delhi|pune|chennai|noida|"
    r"australia|sydney|melbourne|"
    r"netherlands|amsterdam|germany|berlin|munich|france|paris|"
    r"singapore|japan|tokyo|brazil|s[aã]o paulo|argentina|mexico|"
    r"spain|madrid|barcelona|italy|sweden|stockholm|poland|warsaw|"
    r"israel|tel aviv|switzerland|zurich|ph?ilippines|manila|"
    r"china|hong kong|korea|seoul|taiwan|emea|apac|latam)\b",
    re.I,
)

_HIGH_EXP = re.compile(
    r"\b([3-9]\d*|\d{2,})\+?\s*(?:to\s*\d+\s*)?years?\s+(?:of\s+)?(?:professional\s+)?experience\b"
    r"|\bminimum\s+[3-9]\d*\s+years?\b"
    r"|\b[3-9]\+\s*yrs?\b",
    re.I,
)

# Seniority signals checked against job TITLE only.
# All of these are out of reach for the candidate's profile (MS in CS,
# ~1.5 yrs intern + 4 mo Wequity). Senior/Sr./Lead/Architect/Staff/Principal
# postings all want 5+ yrs. Management roles want people leadership.
# Note: `\b` after `\+?` / `\.?` fails (non-word + non-word boundary), so the
# senior-IC alternation uses explicit non-word lookarounds instead.
_SENIOR_TITLE = re.compile(
    r"(?<!\w)(senior|sr\.?|staff\+?|principal|distinguished|fellow|lead|architect)(?!\w)"
    r"|\b(engineering\s+manager|senior\s+manager|senior\s+staff|tech\s+lead)\b"
    r"|\b(director|vp|vice\s+president|head\s+of|cto|ceo|cso|ciso)\b",
    re.I,
)

# Wrong role type — checked against TITLE only so we don't reject SWE JDs that
# mention "work with sales teams" etc. in the description.
# Exceptions: "Sales Engineer", "Solutions Engineer", "Developer Relations",
# "Technical Recruiter", "Revenue Engineer" are technical and kept.
_WRONG_ROLE_TITLE = re.compile(
    # Sales (non-technical)
    r"\b(account\s+executive|account\s+manager|sales\s+development|"
    r"business\s+development\s+rep|SDR|BDR|AE\b|"
    r"enterprise\s+sales|commercial\s+sales|inside\s+sales|"
    r"field\s+sales|sales\s+manager|sales\s+lead)\b"
    # Marketing
    r"|\b(marketing\s+manager|growth\s+marketing|demand\s+(gen|generation)|"
    r"content\s+market|brand\s+market|product\s+market(?!ing\s+engineer)|"
    r"communications\s+manager|social\s+media|copywriter|copy\s+lead|"
    r"media\s+engineer|motion\s+designer|creative\s+studio)\b"
    # HR / People / Recruiting (keep "technical recruiter" to avoid false positives)
    r"|\b(recruiter(?!\s+engineer)|talent\s+acquisition|talent\s+partner|"
    r"people\s+partner|hr\s+business|hrbp|people\s+ops(?!.*engineer)|"
    r"compensation\s+partner|payroll|benefits\s+lead|talent\s+development)\b"
    # Finance / Accounting / Legal
    r"|\b(accountant|accounting\s+(manager|ops|lead)|controller|"
    r"finance\s+(manager|analyst|partner)|fp&a|treasury|"
    r"counsel|legal\s+(ops|counsel)|contracts\s+manager|compliance\s+manager)\b"
    # IT ops / helpdesk / field tech (non-SWE)
    r"|\b(it\s+(support|ops|operations|technician|specialist|analyst)|"
    r"desktop\s+support|helpdesk|help\s+desk|field\s+technician|"
    r"network\s+technician|av\s+technician|it\s+coordinator)\b"
    # Customer success / support (non-technical variants)
    r"|\b(customer\s+success\s+manager|customer\s+support\s+specialist|"
    r"support\s+specialist|customer\s+service)\b",
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
    location = (job.get("location") or "").strip()
    if location and _NON_US_LOCATION.search(location):
        return 0, f"non-US location: {location}"
    if job.get("sponsorship") in {"Does Not Offer Sponsorship", "U.S. Citizenship is Required"}:
        return 0, "no sponsorship"
    if _INTERNSHIP.search(title):
        return 0, "internship"
    if _SENIOR_TITLE.search(title):
        return 0, f"too senior: {_SENIOR_TITLE.search(title).group(0).lower()}"
    if _WRONG_ROLE_TITLE.search(title):
        return 0, f"wrong role type: {_WRONG_ROLE_TITLE.search(title).group(0).lower()}"
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


_FIT_SYSTEM = """You are a job-fit screener for a specific candidate profile:
- New grad / early-career software engineer (MS CS, 1 year internship experience)
- Skills: Python, ML/LLM/RAG, backend web, TypeScript, Docker, AWS
- NO experience: team management, offensive security/pentest, IT helpdesk/ops, hardware, sales, finance, HR

Decide whether to REJECT this job posting. Reject if ANY of the following are true:
1. Role requires managing/leading a team of engineers (Engineering Manager, Director, VP, Head of, Team Lead with reports)
2. Role requires 5+ years of specialized experience (security research, pentest, kernel dev, embedded, etc.)
3. Role is IT helpdesk / desktop support / field technician / AV/hardware setup
4. Role is purely non-technical (sales, marketing, HR, finance, legal, recruiting) — unless explicitly a technical variant
5. Role is Staff, Principal, Distinguished, or Fellow level IC (implies 8-12 years experience)
6. Role requires active security clearance or citizenship

Respond with JSON only: {"reject": true/false, "reason": "one short phrase or empty string"}"""


def llm_fit_check(title: str, desc: str) -> tuple[bool, str]:
    """
    Returns (should_reject, reason).
    Uses Gemma via LM Studio. Raises on LLM failure — fail loud rather than
    silently letting a job through when the fit-check itself broke. Caller
    (scanner) lets the scan cycle error and retries on the next interval.
    """
    from job_scanner.llm import call_json
    # Strip HTML, then skip the typical "About Company" boilerplate (first ~300 chars)
    # and grab a meaty slice of the actual requirements section
    clean = re.sub(r"<[^>]+>", " ", desc)
    clean = re.sub(r"\s+", " ", clean).strip()
    excerpt = clean[300:1400].strip() or clean[:1100].strip()
    result = call_json(
        _FIT_SYSTEM,
        f"Job Title: {title}\n\nJob Description (requirements section):\n{excerpt}",
        max_tokens=1024,
        temperature=0.1,
    )
    if not isinstance(result, dict):
        raise RuntimeError(
            f"llm_fit_check: expected dict, got {type(result).__name__}"
        )
    reject = bool(result.get("reject", False))
    reason = str(result.get("reason", "")).strip()
    return reject, reason

"""
Steps 0 + 1 of the pipeline:
  0. Analyse the JD — extract role type, red flags, keywords, match %
  1. Select — decide which projects, title variants, skills to add
"""
from __future__ import annotations
from . import llm
from graph import queries


# ─── STEP 0: JD ANALYSIS ──────────────────────────────────────────────────────

JD_ANALYSIS_SYSTEM = """You are an expert technical recruiter and resume strategist.
Analyse a job description and extract structured information.

Role type IDs (pick exactly one):
  role_fullstack   – Full-Stack SWE (React + backend)
  role_backend     – Backend SWE (APIs, databases, distributed systems)
  role_frontend    – Frontend SWE (React/TypeScript focused)
  role_ml          – ML Engineer (model training, deployment, pipelines)
  role_ai_llm      – AI/LLM Engineer (LLMs, RAG, vision-language models)
  role_data        – Data Engineer (ETL, pipelines, SQL, warehousing)
  role_devops      – DevOps/SRE (Docker, K8s, CI/CD, infra)
  role_cv          – Computer Vision Engineer (YOLO, OpenCV, CUDA)

Red flag IDs (include all that apply):
  itar             – ITAR or export control restrictions
  no_visa          – Explicitly states no visa sponsorship
  clearance        – Requires security clearance
  low_salary       – Stated salary or range below $100K USD

Output JSON with exactly these keys:
{
  "role_type": "<role_id>",
  "red_flags": ["<flag_id>", ...],
  "company_name": "<company name>",
  "position_title": "<job title>",
  "required_keywords": ["keyword1", "keyword2", ...],
  "preferred_keywords": ["keyword1", ...],
  "jd_summary": "<2-sentence summary of what the role does>",
  "match_percent_before": <0-100 integer estimate before optimization>
}"""


def analyse_jd(jd_text: str) -> dict:
    result = llm.call_json(JD_ANALYSIS_SYSTEM, f"JOB DESCRIPTION:\n\n{jd_text}")
    if not isinstance(result, dict):
        result = {}
    result.setdefault("red_flags", [])
    result.setdefault("required_keywords", [])
    result.setdefault("preferred_keywords", [])
    return result


# ─── STEP 1: SELECTION ────────────────────────────────────────────────────────

SELECTOR_SYSTEM = """You are a resume strategist selecting which content to include in a tailored resume.

You will receive:
- A job description analysis (role type, keywords)
- A list of projects with their tech stacks, categories, and metric status
- The candidate's 3 work experiences

Your job is to SELECT and CONFIGURE — not write content.

RULES:
- Select EXACTLY 3 projects. No more, no less — the resume must fit on one page.
- STRONGLY prefer projects marked [has metrics] — concrete numbers make bullets credible.
  Only pick a no-metrics project if it is significantly more relevant to the JD than any metrics project.
- Among metric projects, prefer those whose tech overlaps most with JD keywords.
  Use role_priority and jd_score as tiebreakers.
- HPE title must be one of:
    "Software Engineer Intern" | "Machine Learning Engineer Intern" |
    "AI Research Engineer" | "Data Engineer Intern" | "Computer Vision Engineer Intern"
- ONGC title must be one of:
    "Software Engineer Intern" | "Data Science Intern"
- skills_to_add: only add skills the candidate genuinely has exposure to.
  Use truthfulness note ("used in project X" or "academic exposure").
  Do not invent. Max 5 additions.
- courses_to_add: choose from the provided course list only. Max 4.
- reasoning: one sentence explaining your project selection logic.

Output JSON with exactly these keys:
{
  "selected_project_ids": ["proj_id_1", "proj_id_2", "proj_id_3"],
  "hpe_title": "<exact title string>",
  "ongc_title": "<exact title string>",
  "skills_to_add": [
    {"name": "<skill>", "category": "<category>", "note": "<truthfulness note>"}
  ],
  "courses_to_add": ["<course name>", ...],
  "reasoning": "<one sentence>"
}"""


def select(jd_analysis: dict) -> dict:
    role_id = jd_analysis.get("role_type", "role_fullstack")
    role = queries.get_role_type(role_id)
    all_projects = queries.get_all_projects()
    courses = queries.get_courses()

    all_keywords = (
        jd_analysis.get("required_keywords", [])
        + jd_analysis.get("preferred_keywords", [])
    )

    scored_projects = []
    for p in all_projects:
        pm = queries.get_project_with_metrics(p["id"])
        has_metrics = bool(pm.get("metrics"))
        score = queries.score_project_for_jd(p["id"], all_keywords)
        scored_projects.append({
            "id": p["id"],
            "name": p["name"],
            "category": p["category"],
            "tech": p["tech"],
            "description": p["description"],
            "jd_score": score,
            "has_metrics": has_metrics,
            "role_priority": (
                role["project_priority"].index(p["id"]) + 1
                if p["id"] in role["project_priority"]
                else 99
            ),
        })

    # Sort: metric projects first, then role priority, then jd score
    scored_projects.sort(key=lambda x: (
        0 if x["has_metrics"] else 1,
        x["role_priority"],
        -x["jd_score"],
    ))

    user_prompt = f"""JD ANALYSIS:
Role type: {role_id} ({role['name']})
Company: {jd_analysis.get('company_name', 'Unknown')}
Position: {jd_analysis.get('position_title', 'Unknown')}
Required keywords: {', '.join(jd_analysis.get('required_keywords', []))}
Preferred keywords: {', '.join(jd_analysis.get('preferred_keywords', []))}
Role emphasis: {', '.join(role.get('emphasis', []))}

PROJECTS (metric projects listed first — strongly prefer [has metrics]):
{_fmt_projects(scored_projects)}

AVAILABLE COURSES:
{', '.join(c['name'] for c in courses)}

ROLE DEFAULT TITLES:
  HPE default: {role['hpe_title']}
  ONGC default: {role['ongc_title']}"""

    result = llm.call_json(SELECTOR_SYSTEM, user_prompt)
    if not isinstance(result, dict):
        result = {}

    # Clamp to exactly 3 — enforce hard page limit
    picked = result.get("selected_project_ids") or []
    if len(picked) != 3:
        # Fall back: top-3 from sorted list (metrics first)
        picked = [p["id"] for p in scored_projects[:3]]
    result["selected_project_ids"] = picked[:3]

    result.setdefault("hpe_title", role["hpe_title"])
    result.setdefault("ongc_title", role["ongc_title"])
    result.setdefault("skills_to_add", [])
    result.setdefault("courses_to_add", [])
    return result


def _fmt_projects(projects: list[dict]) -> str:
    lines = []
    for p in projects:
        metrics_tag = "[has metrics] " if p["has_metrics"] else "[no metrics]  "
        lines.append(
            f"  {metrics_tag}[{p['id']}] {p['name']} | Category: {p['category']} "
            f"| Tech: {', '.join(p['tech'][:6])} "
            f"| JD score: {p['jd_score']} | Role priority rank: {p['role_priority']}"
        )
    return "\n".join(lines)

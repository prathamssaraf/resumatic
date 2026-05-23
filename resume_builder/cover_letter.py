"""
Cover letter generator.
Exactly 1 page, 400-500 words, 5 paragraphs + closing.
"""
from __future__ import annotations
from graph import queries
from . import llm


_COVER_SYSTEM = """You are writing a professional cover letter for a software engineer.

STRUCTURE (5 paragraphs — non-negotiable):
1. Hook (3-4 sentences): Role + company excitement + top 3 qualifications WITH METRICS + key technical fit
2. Professional Experience (4-5 sentences): HPE deep dive — specific achievement with metric, tech stack match, collaboration
3. Technical Fit (4-5 sentences): Projects/research matching their tech — specific technical depth, quantifiable results
4. Culture/Collaboration (3-4 sentences): TA experience (120+ students), teamwork, values alignment
5. Mission Alignment (2-3 sentences): Why this company/product resonates, forward-looking contribution

ABSOLUTE RULES:
- Total word count: 400-500 words (EXACTLY 1 page when printed)
- Every paragraph must contain at least one metric
- LOCKED METRICS must appear verbatim: {metrics_placeholder}
- Mirror the JD's language — use their exact terminology
- No generic platitudes ("I am a passionate developer")
- No em dashes (—) — use regular hyphens or rewrite
- Be specific, enthusiastic, and direct

Output a JSON array of 5 paragraph strings (no greeting, no closing — those are handled separately):
["paragraph 1 text", "paragraph 2 text", ..., "paragraph 5 text"]"""


def generate(jd_analysis: dict, selection: dict) -> list[str]:
    candidate = queries.get_candidate()
    experiences = queries.get_experiences()
    hpe = next(e for e in experiences if "HPE" in e["company"])
    hpe_metrics = queries.get_experience_metrics("exp_hpe")
    selected_projects = [
        queries.get_project_with_metrics(pid)
        for pid in selection.get("selected_project_ids", [])[:2]
        if queries.get_project_with_metrics(pid)
    ]

    key_metrics = [f"{m['label']}: {m['value']}" for m in hpe_metrics[:4]]
    for p in selected_projects:
        for m in p.get("metrics", [])[:2]:
            key_metrics.append(f"{p['name']} {m['label']}: {m['value']}")

    system = _COVER_SYSTEM.replace(
        "{metrics_placeholder}",
        "; ".join(key_metrics[:6]),
    )

    all_kw = (
        jd_analysis.get("required_keywords", [])
        + jd_analysis.get("preferred_keywords", [])
    )
    proj_summaries = "\n".join(
        f"  - {p['name']}: {p['description'][:100]}"
        for p in selected_projects
    )

    user_prompt = f"""COMPANY: {jd_analysis.get('company_name', 'the company')}
POSITION: {jd_analysis.get('position_title', 'Software Engineer')}
JD SUMMARY: {jd_analysis.get('jd_summary', '')}
JD KEYWORDS: {', '.join(all_kw[:20])}
ROLE TYPE: {jd_analysis.get('role_type', '')}

HPE EXPERIENCE:
  Title: {selection.get('hpe_title', 'Software Engineer Intern')}
  Key bullets: {hpe['bullets'][0][:200]}
  Metrics: {', '.join(key_metrics[:4])}

SELECTED PROJECTS:
{proj_summaries}

NYU: Masters CS, GPA 3.92/4.0, TA for 120+ students in Deep Learning"""

    return llm.call_json_list(system, user_prompt, max_tokens=131072)

"""
Technical Skills section.
K2 builds the category structure from the graph skills pool.
Always exactly 7 categories. Category names adapt to the role type.
"""
from __future__ import annotations
from graph import queries
from .. import llm
from ..utils import tex_escape


_SKILLS_SYSTEM = """You are building the Technical Skills section for a resume.
You receive a pool of skills the candidate actually has, plus additional skills to add.

RULES:
1. Use ONLY skills from the provided pool plus skills_to_add. Do not invent skills.
2. Output EXACTLY 7 categories.
3. Category names should reflect the role type (e.g. for ML: "Machine Learning & AI"
   not the generic "Backend & Databases").
4. Order categories by the role_skills_order provided — that is the priority order.
5. Each category: 4-10 items. Include proficiency notes like "(proficient)" or "(familiar)"
   only for skills that have those notes in the pool.
6. Put the most JD-relevant skills first within each category.
7. Do not duplicate skills across categories.

Output JSON:
{
  "categories": [
    {"name": "<category label>", "items": ["Skill1 (proficient)", "Skill2", ...]},
    ...  // exactly 7 items in this array
  ]
}"""


def render(jd_analysis: dict, selection: dict) -> str:
    role_id = jd_analysis.get("role_type", "role_fullstack")
    role = queries.get_role_type(role_id)
    all_skills = queries.get_skills()
    skills_to_add = selection.get("skills_to_add", [])
    all_kw = (
        jd_analysis.get("required_keywords", [])
        + jd_analysis.get("preferred_keywords", [])
    )

    kw_set = {k.lower() for k in all_kw}
    pool_lines = []
    for s in all_skills:
        prof = f" ({s['proficiency']})" if s["proficiency"] not in ("proficient", "") else ""
        # Mark JD-matching skills so K2 knows to prioritise them
        jd_flag = " *" if s["name"].lower() in kw_set else ""
        pool_lines.append(f"  {s['name']}{prof}{jd_flag} [{s['category']}]")

    add_lines = [
        f"  {s['name']} [{s['category']}] — {s.get('note', '')}"
        for s in skills_to_add
    ]

    user_prompt = f"""ROLE TYPE: {role_id} ({role['name']})
ROLE SKILLS ORDER (use this as category priority):
{chr(10).join(f'  {i+1}. {cat}' for i, cat in enumerate(role['skills_order']))}

JD KEYWORDS (prioritise skills matching these): {', '.join(all_kw[:20])}

SKILLS POOL (only use these):
{chr(10).join(pool_lines)}

SKILLS TO ADD (truthful additions approved by selector):
{chr(10).join(add_lines) if add_lines else '  none'}"""

    try:
        generated = llm.call_json(_SKILLS_SYSTEM, user_prompt, max_tokens=131072)
        categories = generated.get("categories", []) if isinstance(generated, dict) else []
    except Exception:
        categories = []

    # Fallback: build from graph directly if K2 output is malformed
    if len(categories) < 7:
        categories = _fallback_categories(role, all_skills, skills_to_add)

    parts = ["\n    \\section{Technical Skills}\n"]
    for cat in categories[:7]:
        name = tex_escape(cat.get("name", "Skills"))
        items = ", ".join(tex_escape(i) for i in cat.get("items", []))
        parts.append(
            f"\n        \\begin{{onecolentry}}\n"
            f"            \\textbf{{{name}:}} {items}\n"
            f"        \\end{{onecolentry}}\n"
            f"\n        \\vspace{{0.05 cm}}\n"
        )

    return "".join(parts)


def _fallback_categories(role: dict, all_skills: list[dict], extras: list[dict]) -> list[dict]:
    """Build 7 categories directly from graph without K2."""
    grouped: dict[str, list[str]] = {}
    for s in all_skills:
        grouped.setdefault(s["category"], []).append(s["name"])
    for s in extras:
        grouped.setdefault(s["category"], []).append(s["name"])

    order = role.get("skills_order", list(grouped.keys()))
    cats = []
    for cat_name in order[:7]:
        items = grouped.get(cat_name, [])
        if items:
            cats.append({"name": cat_name, "items": items})
    # Pad to 7 if needed
    for cat_name, items in grouped.items():
        if len(cats) >= 7:
            break
        if cat_name not in order:
            cats.append({"name": cat_name, "items": items})
    return cats[:7]

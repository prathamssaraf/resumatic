"""
Query interface for the knowledge graph.
All resume-builder logic reads profile data through here.
"""

from __future__ import annotations
import kuzu
from .db import get_db


def _conn() -> kuzu.Connection:
    return get_db()


# ─── PROFILE ──────────────────────────────────────────────────────────────────

def get_candidate() -> dict:
    r = _conn().execute("MATCH (c:Candidate {id: 'pratham'}) RETURN c.*")
    row = r.get_next()
    keys = ["id", "name", "email", "phone", "location", "github"]
    return dict(zip(keys, row))


def get_education() -> list[dict]:
    r = _conn().execute(
        "MATCH (c:Candidate {id: 'pratham'})-[:STUDIED_AT]->(e:Education) "
        "RETURN e.id, e.school, e.degree, e.field, e.location, "
        "e.start_date, e.end_date, e.gpa, e.gpa_scale, e.courses, e.honors "
        "ORDER BY e.end_date DESC"
    )
    results = []
    while r.has_next():
        row = r.get_next()
        results.append({
            "id": row[0], "school": row[1], "degree": row[2], "field": row[3],
            "location": row[4], "start_date": row[5], "end_date": row[6],
            "gpa": row[7], "gpa_scale": row[8], "courses": row[9], "honors": row[10],
        })
    return results


def get_experiences() -> list[dict]:
    r = _conn().execute(
        "MATCH (c:Candidate {id: 'pratham'})-[:WORKED_AT]->(e:Experience) "
        "RETURN e.id, e.company, e.title, e.location, e.start_date, e.end_date, "
        "e.bullets, e.metrics "
        "ORDER BY e.end_date DESC"
    )
    results = []
    while r.has_next():
        row = r.get_next()
        results.append({
            "id": row[0], "company": row[1], "title": row[2], "location": row[3],
            "start_date": row[4], "end_date": row[5], "bullets": row[6], "metrics": row[7],
        })
    return results


def get_experience_metrics(exp_id: str) -> list[dict]:
    r = _conn().execute(
        "MATCH (e:Experience {id: $id})-[:EXP_HAS_METRIC]->(m:Metric) "
        "RETURN m.id, m.label, m.value, m.context",
        {"id": exp_id},
    )
    results = []
    while r.has_next():
        row = r.get_next()
        results.append({"id": row[0], "label": row[1], "value": row[2], "context": row[3]})
    return results


def get_all_metrics() -> list[dict]:
    """Return every locked metric — used for QA checks."""
    r = _conn().execute(
        "MATCH (m:Metric) RETURN m.id, m.source, m.label, m.value, m.context"
    )
    results = []
    while r.has_next():
        row = r.get_next()
        results.append({"id": row[0], "source": row[1], "label": row[2], "value": row[3], "context": row[4]})
    return results


def get_skills(category: str | None = None) -> list[dict]:
    if category:
        r = _conn().execute(
            "MATCH (c:Candidate {id: 'pratham'})-[:HAS_SKILL]->(s:Skill) "
            "WHERE s.category = $cat "
            "RETURN s.id, s.name, s.category, s.proficiency",
            {"cat": category},
        )
    else:
        r = _conn().execute(
            "MATCH (c:Candidate {id: 'pratham'})-[:HAS_SKILL]->(s:Skill) "
            "RETURN s.id, s.name, s.category, s.proficiency "
            "ORDER BY s.category, s.name"
        )
    results = []
    while r.has_next():
        row = r.get_next()
        results.append({"id": row[0], "name": row[1], "category": row[2], "proficiency": row[3]})
    return results


def get_skills_by_order(skills_order: list[str]) -> dict[str, list[dict]]:
    """Return skills grouped by category, in the given order."""
    all_skills = get_skills()
    grouped: dict[str, list[dict]] = {}
    for cat in skills_order:
        grouped[cat] = [s for s in all_skills if s["category"] == cat]
    return grouped


def get_all_projects() -> list[dict]:
    r = _conn().execute(
        "MATCH (c:Candidate {id: 'pratham'})-[:BUILT]->(p:Project) "
        "RETURN p.id, p.name, p.description, p.tech, p.metrics, "
        "p.github, p.category, p.loc, p.commits"
    )
    results = []
    while r.has_next():
        row = r.get_next()
        results.append({
            "id": row[0], "name": row[1], "description": row[2], "tech": row[3],
            "metrics_ids": row[4], "github": row[5], "category": row[6],
            "loc": row[7], "commits": row[8],
        })
    return results


def get_project_with_metrics(proj_id: str) -> dict | None:
    r = _conn().execute(
        "MATCH (p:Project {id: $id}) "
        "RETURN p.id, p.name, p.description, p.tech, p.github, p.category",
        {"id": proj_id},
    )
    if not r.has_next():
        return None
    row = r.get_next()
    proj = {
        "id": row[0], "name": row[1], "description": row[2],
        "tech": row[3], "github": row[4], "category": row[5],
    }
    mr = _conn().execute(
        "MATCH (p:Project {id: $id})-[:PROJECT_HAS_METRIC]->(m:Metric) "
        "RETURN m.label, m.value, m.context",
        {"id": proj_id},
    )
    proj["metrics"] = []
    while mr.has_next():
        mrow = mr.get_next()
        proj["metrics"].append({"label": mrow[0], "value": mrow[1], "context": mrow[2]})
    return proj


def get_role_type(role_id: str) -> dict | None:
    r = _conn().execute(
        "MATCH (rt:RoleType {id: $id}) "
        "RETURN rt.id, rt.name, rt.description, rt.hpe_title, rt.ongc_title, "
        "rt.skills_order, rt.project_priority, rt.emphasis",
        {"id": role_id},
    )
    if not r.has_next():
        return None
    row = r.get_next()
    return {
        "id": row[0], "name": row[1], "description": row[2],
        "hpe_title": row[3], "ongc_title": row[4],
        "skills_order": row[5], "project_priority": row[6], "emphasis": row[7],
    }


def get_all_role_types() -> list[dict]:
    r = _conn().execute(
        "MATCH (rt:RoleType) "
        "RETURN rt.id, rt.name, rt.skills_order, rt.project_priority"
    )
    results = []
    while r.has_next():
        row = r.get_next()
        results.append({"id": row[0], "name": row[1], "skills_order": row[2], "project_priority": row[3]})
    return results


def get_role_keywords(role_id: str, priority: str | None = None) -> list[dict]:
    if priority:
        r = _conn().execute(
            "MATCH (rt:RoleType {id: $rid})-[:ROLE_HAS_KEYWORD]->(k:Keyword) "
            "WHERE k.priority = $p "
            "RETURN k.term, k.priority",
            {"rid": role_id, "p": priority},
        )
    else:
        r = _conn().execute(
            "MATCH (rt:RoleType {id: $rid})-[:ROLE_HAS_KEYWORD]->(k:Keyword) "
            "RETURN k.term, k.priority "
            "ORDER BY k.priority",
            {"rid": role_id},
        )
    results = []
    while r.has_next():
        row = r.get_next()
        results.append({"term": row[0], "priority": row[1]})
    return results


def get_projects_for_role(role_id: str) -> list[dict]:
    """Return projects in priority order for a given role type, with metrics."""
    r = _conn().execute(
        "MATCH (rt:RoleType {id: $rid})-[rel:ROLE_PREFERS_PROJECT]->(p:Project) "
        "RETURN p.id, p.name, p.description, p.tech, p.category, rel.rank "
        "ORDER BY rel.rank ASC",
        {"rid": role_id},
    )
    results = []
    while r.has_next():
        row = r.get_next()
        proj = {
            "id": row[0], "name": row[1], "description": row[2],
            "tech": row[3], "category": row[4], "rank": row[5],
        }
        proj_full = get_project_with_metrics(proj["id"])
        if proj_full:
            proj["metrics"] = proj_full["metrics"]
        results.append(proj)
    return results


def get_courses(school: str | None = None) -> list[dict]:
    if school:
        r = _conn().execute(
            "MATCH (e:Education {id: $eid})-[:TOOK]->(cr:Course) "
            "RETURN cr.name, cr.keywords",
            {"eid": f"edu_{school.lower()}"},
        )
    else:
        r = _conn().execute("MATCH (cr:Course) RETURN cr.name, cr.school, cr.keywords")
    results = []
    while r.has_next():
        row = r.get_next()
        results.append({"name": row[0], "school": row[1] if not school else school, "keywords": row[-1]})
    return results


def score_project_for_jd(proj_id: str, jd_keywords: list[str]) -> int:
    """
    Simple deterministic scorer: counts how many JD keywords appear
    in a project's tech stack and description. Returns 0-100.
    """
    proj = get_project_with_metrics(proj_id)
    if not proj:
        return 0
    text = " ".join([proj["description"]] + proj["tech"]).lower()
    hits = sum(1 for kw in jd_keywords if kw.lower() in text)
    return min(100, int((hits / max(len(jd_keywords), 1)) * 100))


def get_full_profile() -> dict:
    """Return the complete profile as a single dict — used for LLM context."""
    return {
        "candidate": get_candidate(),
        "education": get_education(),
        "experiences": get_experiences(),
        "skills": get_skills(),
        "projects": [get_project_with_metrics(p["id"]) for p in get_all_projects()],
        "metrics": get_all_metrics(),
        "role_types": get_all_role_types(),
    }

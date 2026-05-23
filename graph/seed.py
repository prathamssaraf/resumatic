"""
Seeds the Kuzu graph database with all of Pratham's profile data.
Run: uv run python -m graph.seed
"""

import kuzu
from .db import init_db
from .schema import create_schema
from .seed_data import (
    CANDIDATE, EDUCATION, COURSES, EXPERIENCES, METRICS,
    PROJECTS, SKILLS, ROLE_TYPES, KEYWORDS,
    PROJECT_METRICS_MAP, EXPERIENCE_METRICS_MAP,
    EXPERIENCE_SKILLS_MAP, PROJECT_SKILLS_MAP,
)


def _q(conn: kuzu.Connection, cypher: str, params: dict | None = None) -> None:
    if params:
        conn.execute(cypher, params)
    else:
        conn.execute(cypher)


def seed_candidate(conn: kuzu.Connection) -> None:
    c = CANDIDATE
    _q(conn,
        "MERGE (c:Candidate {id: $id}) "
        "SET c.name=$name, c.email=$email, c.phone=$phone, c.location=$location, c.github=$github",
        c,
    )


def seed_education(conn: kuzu.Connection) -> None:
    for e in EDUCATION:
        _q(conn,
            "MERGE (e:Education {id: $id}) "
            "SET e.school=$school, e.degree=$degree, e.field=$field, e.location=$location, "
            "e.start_date=$start_date, e.end_date=$end_date, e.gpa=$gpa, "
            "e.gpa_scale=$gpa_scale, e.courses=$courses, e.honors=$honors",
            e,
        )
        _q(conn,
            "MATCH (c:Candidate {id: 'pratham'}), (e:Education {id: $id}) "
            "MERGE (c)-[:STUDIED_AT]->(e)",
            {"id": e["id"]},
        )

    for course in COURSES:
        _q(conn,
            "MERGE (cr:Course {id: $id}) "
            "SET cr.name=$name, cr.school=$school, cr.keywords=$keywords",
            course,
        )
        edu_id = "edu_nyu" if course["school"] == "NYU" else "edu_manipal"
        _q(conn,
            "MATCH (e:Education {id: $edu_id}), (cr:Course {id: $course_id}) "
            "MERGE (e)-[:TOOK]->(cr)",
            {"edu_id": edu_id, "course_id": course["id"]},
        )


def seed_skills(conn: kuzu.Connection) -> None:
    for s in SKILLS:
        _q(conn,
            "MERGE (sk:Skill {id: $id}) "
            "SET sk.name=$name, sk.category=$category, sk.proficiency=$proficiency",
            s,
        )
        _q(conn,
            "MATCH (c:Candidate {id: 'pratham'}), (sk:Skill {id: $id}) "
            "MERGE (c)-[:HAS_SKILL]->(sk)",
            {"id": s["id"]},
        )


def seed_metrics(conn: kuzu.Connection) -> None:
    for m in METRICS:
        _q(conn,
            "MERGE (m:Metric {id: $id}) "
            "SET m.source=$source, m.label=$label, m.value=$value, m.context=$context",
            m,
        )


def seed_experiences(conn: kuzu.Connection) -> None:
    for exp in EXPERIENCES:
        _q(conn,
            "MERGE (e:Experience {id: $id}) "
            "SET e.company=$company, e.title=$title, e.location=$location, "
            "e.start_date=$start_date, e.end_date=$end_date, "
            "e.bullets=$bullets, e.metrics=$metrics",
            exp,
        )
        _q(conn,
            "MATCH (c:Candidate {id: 'pratham'}), (e:Experience {id: $id}) "
            "MERGE (c)-[:WORKED_AT]->(e)",
            {"id": exp["id"]},
        )
        for metric_id in EXPERIENCE_METRICS_MAP.get(exp["id"], []):
            _q(conn,
                "MATCH (e:Experience {id: $exp_id}), (m:Metric {id: $metric_id}) "
                "MERGE (e)-[:EXP_HAS_METRIC]->(m)",
                {"exp_id": exp["id"], "metric_id": metric_id},
            )
        for skill_id in EXPERIENCE_SKILLS_MAP.get(exp["id"], []):
            _q(conn,
                "MATCH (e:Experience {id: $exp_id}), (sk:Skill {id: $skill_id}) "
                "MERGE (e)-[:EXP_USES]->(sk)",
                {"exp_id": exp["id"], "skill_id": skill_id},
            )


def seed_projects(conn: kuzu.Connection) -> None:
    for proj in PROJECTS:
        _q(conn,
            "MERGE (p:Project {id: $id}) "
            "SET p.name=$name, p.description=$description, p.tech=$tech, "
            "p.metrics=$metrics, p.github=$github, p.category=$category, "
            "p.loc=$loc, p.commits=$commits",
            {**proj, "metrics": proj.get("metrics", [])},
        )
        _q(conn,
            "MATCH (c:Candidate {id: 'pratham'}), (p:Project {id: $id}) "
            "MERGE (c)-[:BUILT]->(p)",
            {"id": proj["id"]},
        )
        for metric_id in PROJECT_METRICS_MAP.get(proj["id"], []):
            _q(conn,
                "MATCH (p:Project {id: $proj_id}), (m:Metric {id: $metric_id}) "
                "MERGE (p)-[:PROJECT_HAS_METRIC]->(m)",
                {"proj_id": proj["id"], "metric_id": metric_id},
            )
        for skill_id in PROJECT_SKILLS_MAP.get(proj["id"], []):
            _q(conn,
                "MATCH (p:Project {id: $proj_id}), (sk:Skill {id: $skill_id}) "
                "MERGE (p)-[:PROJECT_USES]->(sk)",
                {"proj_id": proj["id"], "skill_id": skill_id},
            )


def seed_role_types(conn: kuzu.Connection) -> None:
    for role in ROLE_TYPES:
        _q(conn,
            "MERGE (r:RoleType {id: $id}) "
            "SET r.name=$name, r.description=$description, "
            "r.hpe_title=$hpe_title, r.ongc_title=$ongc_title, "
            "r.skills_order=$skills_order, r.project_priority=$project_priority, "
            "r.emphasis=$emphasis",
            role,
        )
        for rank, proj_id in enumerate(role["project_priority"], start=1):
            _q(conn,
                "MATCH (r:RoleType {id: $role_id}), (p:Project {id: $proj_id}) "
                "MERGE (r)-[rel:ROLE_PREFERS_PROJECT]->(p) "
                "SET rel.rank=$rank",
                {"role_id": role["id"], "proj_id": proj_id, "rank": rank},
            )


def seed_keywords(conn: kuzu.Connection) -> None:
    for kw in KEYWORDS:
        _q(conn,
            "MERGE (k:Keyword {id: $id}) "
            "SET k.term=$term, k.role_type=$role_type, k.priority=$priority",
            kw,
        )
        _q(conn,
            "MATCH (r:RoleType {id: $role_id}), (k:Keyword {id: $kw_id}) "
            "MERGE (r)-[:ROLE_HAS_KEYWORD]->(k)",
            {"role_id": kw["role_type"], "kw_id": kw["id"]},
        )


def run() -> None:
    from rich.console import Console
    from rich.progress import track

    console = Console()
    console.print("\n[bold cyan]Building Pratham's Knowledge Graph[/bold cyan]\n")

    conn = init_db()
    create_schema(conn)
    console.print("[green]✓[/green] Schema created")

    steps = [
        ("Candidate", seed_candidate),
        ("Education + Courses", seed_education),
        ("Skills", seed_skills),
        ("Metrics (immutable)", seed_metrics),
        ("Experiences", seed_experiences),
        ("Projects", seed_projects),
        ("Role Types", seed_role_types),
        ("Keywords", seed_keywords),
    ]

    for label, fn in track(steps, description="Seeding..."):
        fn(conn)

    console.print("\n[bold green]✓ Knowledge graph built successfully![/bold green]")

    # Print summary
    tables = [
        ("Candidate", "MATCH (n:Candidate) RETURN count(n)"),
        ("Skills", "MATCH (n:Skill) RETURN count(n)"),
        ("Projects", "MATCH (n:Project) RETURN count(n)"),
        ("Experiences", "MATCH (n:Experience) RETURN count(n)"),
        ("Education", "MATCH (n:Education) RETURN count(n)"),
        ("Courses", "MATCH (n:Course) RETURN count(n)"),
        ("Metrics", "MATCH (n:Metric) RETURN count(n)"),
        ("Role Types", "MATCH (n:RoleType) RETURN count(n)"),
        ("Keywords", "MATCH (n:Keyword) RETURN count(n)"),
    ]
    console.print("\n[bold]Node counts:[/bold]")
    for label, query in tables:
        result = conn.execute(query)
        count = result.get_next()[0]
        console.print(f"  {label:25s} {count}")

    rel_counts = [
        ("HAS_SKILL", "MATCH ()-[r:HAS_SKILL]->() RETURN count(r)"),
        ("BUILT", "MATCH ()-[r:BUILT]->() RETURN count(r)"),
        ("WORKED_AT", "MATCH ()-[r:WORKED_AT]->() RETURN count(r)"),
        ("PROJECT_USES", "MATCH ()-[r:PROJECT_USES]->() RETURN count(r)"),
        ("EXP_HAS_METRIC", "MATCH ()-[r:EXP_HAS_METRIC]->() RETURN count(r)"),
        ("PROJECT_HAS_METRIC", "MATCH ()-[r:PROJECT_HAS_METRIC]->() RETURN count(r)"),
        ("ROLE_PREFERS_PROJECT", "MATCH ()-[r:ROLE_PREFERS_PROJECT]->() RETURN count(r)"),
        ("ROLE_HAS_KEYWORD", "MATCH ()-[r:ROLE_HAS_KEYWORD]->() RETURN count(r)"),
    ]
    console.print("\n[bold]Relationship counts:[/bold]")
    for label, query in rel_counts:
        result = conn.execute(query)
        count = result.get_next()[0]
        console.print(f"  {label:25s} {count}")


if __name__ == "__main__":
    run()

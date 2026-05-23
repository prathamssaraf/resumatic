"""
Create all Kuzu node and relationship tables.
Run once; safe to re-run (drops then recreates).
"""

import kuzu


NODE_TABLES = [
    # Identity
    """CREATE NODE TABLE IF NOT EXISTS Candidate(
        id STRING PRIMARY KEY,
        name STRING,
        email STRING,
        phone STRING,
        location STRING,
        github STRING
    )""",

    # Skills
    """CREATE NODE TABLE IF NOT EXISTS Skill(
        id STRING PRIMARY KEY,
        name STRING,
        category STRING,
        proficiency STRING
    )""",

    # Work experience entries
    """CREATE NODE TABLE IF NOT EXISTS Experience(
        id STRING PRIMARY KEY,
        company STRING,
        title STRING,
        location STRING,
        start_date STRING,
        end_date STRING,
        bullets STRING[],
        metrics STRING[]
    )""",

    # Portfolio projects
    """CREATE NODE TABLE IF NOT EXISTS Project(
        id STRING PRIMARY KEY,
        name STRING,
        description STRING,
        tech STRING[],
        metrics STRING[],
        github STRING,
        category STRING,
        loc INT64,
        commits INT64
    )""",

    # Education
    """CREATE NODE TABLE IF NOT EXISTS Education(
        id STRING PRIMARY KEY,
        school STRING,
        degree STRING,
        field STRING,
        location STRING,
        start_date STRING,
        end_date STRING,
        gpa STRING,
        gpa_scale STRING,
        courses STRING[],
        honors STRING[]
    )""",

    # Role types (Full-Stack, Backend, ML, etc.)
    """CREATE NODE TABLE IF NOT EXISTS RoleType(
        id STRING PRIMARY KEY,
        name STRING,
        description STRING,
        hpe_title STRING,
        ongc_title STRING,
        skills_order STRING[],
        project_priority STRING[],
        emphasis STRING[]
    )""",

    # Immutable metrics — locked, never overrideable by LLM
    """CREATE NODE TABLE IF NOT EXISTS Metric(
        id STRING PRIMARY KEY,
        source STRING,
        label STRING,
        value STRING,
        context STRING
    )""",

    # Courses
    """CREATE NODE TABLE IF NOT EXISTS Course(
        id STRING PRIMARY KEY,
        name STRING,
        school STRING,
        keywords STRING[]
    )""",

    # Keyword library per role type
    """CREATE NODE TABLE IF NOT EXISTS Keyword(
        id STRING PRIMARY KEY,
        term STRING,
        role_type STRING,
        priority STRING
    )""",
]

REL_TABLES = [
    "CREATE REL TABLE IF NOT EXISTS HAS_SKILL(FROM Candidate TO Skill)",
    "CREATE REL TABLE IF NOT EXISTS WORKED_AT(FROM Candidate TO Experience)",
    "CREATE REL TABLE IF NOT EXISTS BUILT(FROM Candidate TO Project)",
    "CREATE REL TABLE IF NOT EXISTS STUDIED_AT(FROM Candidate TO Education)",
    "CREATE REL TABLE IF NOT EXISTS TOOK(FROM Education TO Course)",
    "CREATE REL TABLE IF NOT EXISTS PROJECT_USES(FROM Project TO Skill)",
    "CREATE REL TABLE IF NOT EXISTS EXP_USES(FROM Experience TO Skill)",
    "CREATE REL TABLE IF NOT EXISTS ROLE_PREFERS_SKILL(FROM RoleType TO Skill, rank INT64)",
    "CREATE REL TABLE IF NOT EXISTS ROLE_PREFERS_PROJECT(FROM RoleType TO Project, rank INT64)",
    "CREATE REL TABLE IF NOT EXISTS EXP_HAS_METRIC(FROM Experience TO Metric)",
    "CREATE REL TABLE IF NOT EXISTS PROJECT_HAS_METRIC(FROM Project TO Metric)",
    "CREATE REL TABLE IF NOT EXISTS ROLE_HAS_KEYWORD(FROM RoleType TO Keyword)",
]


def create_schema(conn: kuzu.Connection) -> None:
    for stmt in NODE_TABLES:
        conn.execute(stmt)
    for stmt in REL_TABLES:
        conn.execute(stmt)

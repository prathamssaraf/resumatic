import kuzu
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "data" / "profile.kuzu"

_conn: kuzu.Connection | None = None


def get_db() -> kuzu.Connection:
    global _conn
    if _conn is None:
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        db = kuzu.Database(str(DB_PATH))
        _conn = kuzu.Connection(db)
    return _conn


def init_db() -> kuzu.Connection:
    """Drop and recreate all tables. Call once during seeding."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = kuzu.Database(str(DB_PATH))
    conn = kuzu.Connection(db)
    global _conn
    _conn = conn
    return conn

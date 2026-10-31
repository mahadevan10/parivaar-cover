"""SQLite storage for chat turns, the family each session builds up, and recommendations.

The database is backend/parivaar.db, or the file named by PARIVAAR_DB. Families are stored as JSON
after the Pydantic models in app.py have checked them, so they stay in the shared/families.json format.
Look at the data with: sqlite3 backend/parivaar.db
"""
import json
import os
import sqlite3
from contextlib import closing
from pathlib import Path

DEFAULT_PATH = Path(__file__).resolve().parent / "parivaar.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS chat_messages (
    id INTEGER PRIMARY KEY,
    session_id TEXT NOT NULL,
    role TEXT NOT NULL,              -- user or assistant
    text TEXT NOT NULL,              -- as said, in any language
    english TEXT,                    -- the English the values were checked against, for user turns
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS chat_messages_session ON chat_messages (session_id, id);

-- The latest family for each session, updated after every chat turn
CREATE TABLE IF NOT EXISTS families (
    session_id TEXT PRIMARY KEY,
    family TEXT NOT NULL,            -- FamilyDraft as JSON
    missing TEXT NOT NULL,           -- JSON list of what is still needed
    ready INTEGER NOT NULL,          -- 1 once nothing is missing
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Every solver run, with the exact family it ran on
CREATE TABLE IF NOT EXISTS recommendations (
    id TEXT PRIMARY KEY,
    alias TEXT,                      -- the id the frontend builds: <family id>-<total premium>
    session_id TEXT,
    family TEXT NOT NULL,            -- Family as JSON, the solver input
    result TEXT NOT NULL,            -- the /recommend response as JSON
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS recommendations_alias ON recommendations (alias);
"""


def connect():
    conn = sqlite3.connect(os.environ.get("PARIVAAR_DB") or DEFAULT_PATH)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    return conn


def add_message(session_id, role, text, english=None):
    with closing(connect()) as conn, conn:
        conn.execute("INSERT INTO chat_messages (session_id, role, text, english) VALUES (?, ?, ?, ?)",
                     (session_id, role, text, english))


def messages(session_id):
    with closing(connect()) as conn:
        rows = conn.execute("SELECT role, text, english, created_at FROM chat_messages WHERE session_id = ? ORDER BY id",
                            (session_id,)).fetchall()
    return [dict(r) for r in rows]


def save_family(session_id, family, missing):
    """family is a FamilyDraft."""
    with closing(connect()) as conn, conn:
        conn.execute("""INSERT INTO families (session_id, family, missing, ready) VALUES (?, ?, ?, ?)
                        ON CONFLICT (session_id) DO UPDATE SET family = excluded.family, missing = excluded.missing,
                        ready = excluded.ready, updated_at = CURRENT_TIMESTAMP""",
                     (session_id, family.model_dump_json(), json.dumps(missing), int(not missing)))


def family(session_id):
    """The latest family for a session as a dict, with missing and ready, or None."""
    with closing(connect()) as conn:
        row = conn.execute("SELECT family, missing, ready FROM families WHERE session_id = ?", (session_id,)).fetchone()
    if row is None:
        return None
    return {"family": json.loads(row["family"]), "missing": json.loads(row["missing"]), "ready": bool(row["ready"])}


def save_recommendation(rec, family, alias=None):
    """rec is the /recommend response, family the Family the solver ran on."""
    with closing(connect()) as conn, conn:
        conn.execute("INSERT INTO recommendations (id, alias, session_id, family, result) VALUES (?, ?, ?, ?, ?)",
                     (rec["id"], alias, family.id, family.model_dump_json(), json.dumps(rec, ensure_ascii=False)))


def recommendation(rec_id):
    """A /recommend response by its id or the frontend's alias, newest first, or None."""
    with closing(connect()) as conn:
        row = conn.execute("SELECT result FROM recommendations WHERE id = ? OR alias = ? ORDER BY created_at DESC, rowid DESC",
                           (rec_id, rec_id)).fetchone()
    return json.loads(row["result"]) if row else None


def recommendation_family(rec_id):
    """The Family a recommendation was solved for, as a dict, or None."""
    with closing(connect()) as conn:
        row = conn.execute("SELECT family FROM recommendations WHERE id = ? OR alias = ? ORDER BY created_at DESC, rowid DESC",
                           (rec_id, rec_id)).fetchone()
    return json.loads(row["family"]) if row else None

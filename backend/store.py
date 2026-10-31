"""SQLite storage for policies, chat turns, the family each session builds up, and recommendations.

The database is backend/parivaar.db, or the file named by PARIVAAR_DB. Families are stored as JSON
after the Pydantic models in app.py have checked them, so they stay in the shared/families.json format.
Policies are loaded from shared/policies.json, which stays the file to edit. The table is rebuilt
whenever the file changes, so an edit shows up on the next read without a restart.
Look at the data with: sqlite3 backend/parivaar.db
"""
import hashlib
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

-- Policies, loaded from shared/policies.json. Edit the JSON; the table is rebuilt when it changes.
-- The columns are for querying; the solver reads the full record in policy.
CREATE TABLE IF NOT EXISTS policies (
    id TEXT PRIMARY KEY,
    position INTEGER NOT NULL,       -- order in policies.json
    insurer TEXT NOT NULL,
    product TEXT NOT NULL,
    plan_type TEXT NOT NULL,         -- floater, individual, senior or super_topup
    sum_insured INTEGER NOT NULL,
    deductible INTEGER NOT NULL,
    entry_age_min INTEGER NOT NULL,
    entry_age_max INTEGER NOT NULL,
    max_members INTEGER,
    copay_percent INTEGER NOT NULL,
    room_rent_capped INTEGER NOT NULL,
    initial_wait_months INTEGER NOT NULL,
    specific_illness_wait_months INTEGER NOT NULL,
    pre_existing_wait_months INTEGER NOT NULL,
    diabetes_wait_months INTEGER NOT NULL,  -- condition_waits_months.diabetes, else pre_existing
    verified INTEGER NOT NULL,
    source TEXT,
    policy TEXT NOT NULL             -- the full policy as JSON
);
CREATE INDEX IF NOT EXISTS policies_plan_type ON policies (plan_type, sum_insured);

CREATE TABLE IF NOT EXISTS meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""

POLICIES_JSON = Path(__file__).resolve().parent.parent / "shared" / "policies.json"


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
    """The Family a recommendation ran on, as a dict, or None."""
    with closing(connect()) as conn:
        row = conn.execute("SELECT family FROM recommendations WHERE id = ?", (rec_id,)).fetchone()
    return json.loads(row["family"]) if row else None


def save_summary(rec_id, summary):
    """Keeps the summary inside the stored /recommend response, so it is written once."""
    with closing(connect()) as conn, conn:
        row = conn.execute("SELECT rowid, result FROM recommendations WHERE id = ?", (rec_id,)).fetchone()
        if row:
            result = dict(json.loads(row["result"]), summary=summary)
            conn.execute("UPDATE recommendations SET result = ? WHERE rowid = ?",
                         (json.dumps(result, ensure_ascii=False), row["rowid"]))


def _policy_row(position, p):
    waits = p["waiting_periods_months"]
    return (p["id"], position, p["insurer"], p["product"], p["plan_type"], p["sum_insured"], p["deductible"],
            p["entry_age"]["min"], p["entry_age"]["max"], p.get("max_members"), p["copay_percent"],
            int(p["room_rent"]["capped"]), waits["initial"], waits["specific_illness"], waits["pre_existing"],
            p["condition_waits_months"].get("diabetes", waits["pre_existing"]), int(p["verified"]), p.get("source"),
            json.dumps(p, ensure_ascii=False))


def sync_policies(conn, path=POLICIES_JSON):
    """Rebuilds the policies table from the JSON file if the file changed since the last load."""
    raw = Path(path).read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    row = conn.execute("SELECT value FROM meta WHERE key = 'policies_sha256'").fetchone()
    if row and row["value"] == digest:
        return
    rows = [_policy_row(i, p) for i, p in enumerate(json.loads(raw)["policies"])]
    with conn:
        conn.execute("DELETE FROM policies")
        conn.executemany(f"INSERT INTO policies VALUES ({', '.join('?' * 19)})", rows)
        conn.execute("INSERT INTO meta (key, value) VALUES ('policies_sha256', ?) "
                     "ON CONFLICT (key) DO UPDATE SET value = excluded.value", (digest,))


def policies():
    """Every policy as a dict in the policies.json format, in file order."""
    with closing(connect()) as conn:
        sync_policies(conn)
        rows = conn.execute("SELECT policy FROM policies ORDER BY position").fetchall()
    return [json.loads(r["policy"]) for r in rows]

"""SQLite schema and CRUD operations."""

import json
import sqlite3
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path

SCHEMA = """
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS sessions (
    id TEXT PRIMARY KEY,
    client_info TEXT NOT NULL DEFAULT '{}',
    started_at TEXT NOT NULL,
    last_seen_at TEXT NOT NULL,
    escalation_level INTEGER NOT NULL DEFAULT 0,
    discovered_hosts TEXT NOT NULL DEFAULT '[]',
    discovered_ports TEXT NOT NULL DEFAULT '[]',
    discovered_files TEXT NOT NULL DEFAULT '[]',
    discovered_credentials TEXT NOT NULL DEFAULT '[]',
    metadata TEXT NOT NULL DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS interactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    method TEXT NOT NULL,
    tool_name TEXT,
    params TEXT NOT NULL DEFAULT '{}',
    response TEXT NOT NULL DEFAULT '{}',
    escalation_delta INTEGER NOT NULL DEFAULT 0,
    FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS honey_tokens (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    token_type TEXT NOT NULL,
    token_value TEXT NOT NULL,
    context TEXT NOT NULL DEFAULT '',
    deployed_at TEXT NOT NULL,
    interaction_id INTEGER,
    FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE,
    FOREIGN KEY (interaction_id) REFERENCES interactions(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_interactions_session ON interactions(session_id);
CREATE INDEX IF NOT EXISTS idx_honey_tokens_session ON honey_tokens(session_id);
CREATE INDEX IF NOT EXISTS idx_honey_tokens_value ON honey_tokens(token_value);
"""


def init_db(db_path: str) -> None:
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path) as conn:
        conn.executescript(SCHEMA)


@contextmanager
def get_connection(db_path: str):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def now_iso() -> str:
    return datetime.now(UTC).isoformat()


def create_session(db_path: str, session_id: str, client_info: dict) -> None:
    ts = now_iso()
    with get_connection(db_path) as conn:
        conn.execute(
            "INSERT INTO sessions (id, client_info, started_at, last_seen_at) VALUES (?, ?, ?, ?)",
            (session_id, json.dumps(client_info), ts, ts),
        )


def update_session(db_path: str, session_id: str, **fields) -> None:
    json_fields = {"discovered_hosts", "discovered_ports", "discovered_files",
                   "discovered_credentials", "metadata"}
    set_parts = ["last_seen_at = ?"]
    values = [now_iso()]
    for key, value in fields.items():
        set_parts.append(f"{key} = ?")
        values.append(json.dumps(value) if key in json_fields else value)
    values.append(session_id)
    with get_connection(db_path) as conn:
        conn.execute(
            f"UPDATE sessions SET {', '.join(set_parts)} WHERE id = ?",
            values,
        )


def get_session(db_path: str, session_id: str) -> dict | None:
    with get_connection(db_path) as conn:
        row = conn.execute("SELECT * FROM sessions WHERE id = ?", (session_id,)).fetchone()
        if row is None:
            return None
        result = dict(row)
        for field in ("client_info", "discovered_hosts", "discovered_ports",
                      "discovered_files", "discovered_credentials", "metadata"):
            result[field] = json.loads(result[field])
        return result


def log_interaction(db_path: str, session_id: str, method: str,
                    tool_name: str | None, params: dict, response: dict,
                    escalation_delta: int = 0) -> int:
    with get_connection(db_path) as conn:
        cursor = conn.execute(
            """INSERT INTO interactions
               (session_id, timestamp, method, tool_name, params, response, escalation_delta)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (session_id, now_iso(), method, tool_name, json.dumps(params),
             json.dumps(response), escalation_delta),
        )
        return cursor.lastrowid


def log_honey_token(db_path: str, session_id: str, token_type: str,
                    token_value: str, context: str, interaction_id: int | None = None) -> int:
    with get_connection(db_path) as conn:
        cursor = conn.execute(
            """INSERT INTO honey_tokens
               (session_id, token_type, token_value, context, deployed_at, interaction_id)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (session_id, token_type, token_value, context, now_iso(), interaction_id),
        )
        return cursor.lastrowid

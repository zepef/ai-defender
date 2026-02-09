"""SQLite schema and CRUD operations."""

import json
import os
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
    # Restrict DB file permissions to owner only
    try:
        os.chmod(db_path, 0o600)
    except OSError:
        pass  # May fail on some platforms (e.g., Windows)


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


_ALLOWED_SESSION_FIELDS = frozenset({
    "escalation_level", "discovered_hosts", "discovered_ports",
    "discovered_files", "discovered_credentials", "metadata",
})
_JSON_SESSION_FIELDS = frozenset({
    "discovered_hosts", "discovered_ports", "discovered_files",
    "discovered_credentials", "metadata",
})


def update_session(db_path: str, session_id: str, **fields) -> None:
    set_parts = ["last_seen_at = ?"]
    values = [now_iso()]
    for key, value in fields.items():
        if key not in _ALLOWED_SESSION_FIELDS:
            raise ValueError(f"Invalid session field: {key}")
        set_parts.append(f"{key} = ?")
        values.append(json.dumps(value) if key in _JSON_SESSION_FIELDS else value)
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


# ---------------------------------------------------------------------------
# Dashboard query functions
# ---------------------------------------------------------------------------

def get_stats(db_path: str) -> dict:
    with get_connection(db_path) as conn:
        total_sessions = conn.execute("SELECT COUNT(*) FROM sessions").fetchone()[0]
        active_sessions = conn.execute(
            "SELECT COUNT(*) FROM sessions WHERE last_seen_at >= datetime('now', '-1 hour')"
        ).fetchone()[0]
        avg_row = conn.execute("SELECT AVG(escalation_level) FROM sessions").fetchone()
        avg_escalation = round(avg_row[0], 2) if avg_row[0] is not None else 0
        total_interactions = conn.execute("SELECT COUNT(*) FROM interactions").fetchone()[0]
        total_tokens = conn.execute("SELECT COUNT(*) FROM honey_tokens").fetchone()[0]

        tool_usage = {}
        for row in conn.execute(
            "SELECT tool_name, COUNT(*) as cnt FROM interactions "
            "WHERE tool_name IS NOT NULL GROUP BY tool_name ORDER BY cnt DESC"
        ):
            tool_usage[row["tool_name"]] = row["cnt"]

        token_type_breakdown = {}
        for row in conn.execute(
            "SELECT token_type, COUNT(*) as cnt FROM honey_tokens "
            "GROUP BY token_type ORDER BY cnt DESC"
        ):
            token_type_breakdown[row["token_type"]] = row["cnt"]

        escalation_distribution = {}
        for row in conn.execute(
            "SELECT escalation_level, COUNT(*) as cnt FROM sessions "
            "GROUP BY escalation_level ORDER BY escalation_level"
        ):
            escalation_distribution[str(row["escalation_level"])] = row["cnt"]

    return {
        "total_sessions": total_sessions,
        "active_sessions": active_sessions,
        "avg_escalation": avg_escalation,
        "total_interactions": total_interactions,
        "total_tokens": total_tokens,
        "tool_usage": tool_usage,
        "token_type_breakdown": token_type_breakdown,
        "escalation_distribution": escalation_distribution,
    }


def get_all_sessions(db_path: str, escalation_level: int | None = None,
                     since: str | None = None, limit: int = 50,
                     offset: int = 0) -> tuple[list[dict], int]:
    where_parts: list[str] = []
    params: list = []
    if escalation_level is not None:
        where_parts.append("s.escalation_level = ?")
        params.append(escalation_level)
    if since:
        where_parts.append("s.started_at >= ?")
        params.append(since)
    where_clause = f"WHERE {' AND '.join(where_parts)}" if where_parts else ""

    with get_connection(db_path) as conn:
        total = conn.execute(
            f"SELECT COUNT(*) FROM sessions s {where_clause}", params
        ).fetchone()[0]

        rows = conn.execute(
            f"""SELECT s.id, s.client_info, s.started_at, s.last_seen_at,
                       s.escalation_level,
                       COUNT(DISTINCT i.id) as interaction_count,
                       COUNT(DISTINCT h.id) as token_count
                FROM sessions s
                LEFT JOIN interactions i ON i.session_id = s.id
                LEFT JOIN honey_tokens h ON h.session_id = s.id
                {where_clause}
                GROUP BY s.id
                ORDER BY s.started_at DESC
                LIMIT ? OFFSET ?""",
            params + [limit, offset],
        ).fetchall()

    sessions = []
    for row in rows:
        d = dict(row)
        d["client_info"] = json.loads(d["client_info"])
        sessions.append(d)
    return sessions, total


def get_session_interactions(db_path: str, session_id: str,
                             limit: int = 100,
                             offset: int = 0) -> tuple[list[dict], int]:
    with get_connection(db_path) as conn:
        total = conn.execute(
            "SELECT COUNT(*) FROM interactions WHERE session_id = ?",
            (session_id,),
        ).fetchone()[0]

        rows = conn.execute(
            """SELECT id, timestamp, method, tool_name, params, response, escalation_delta
               FROM interactions WHERE session_id = ?
               ORDER BY timestamp ASC LIMIT ? OFFSET ?""",
            (session_id, limit, offset),
        ).fetchall()

    interactions = []
    for row in rows:
        d = dict(row)
        d["params"] = json.loads(d["params"])
        d["response"] = json.loads(d["response"])
        interactions.append(d)
    return interactions, total


def get_session_tokens(db_path: str, session_id: str) -> list[dict]:
    with get_connection(db_path) as conn:
        rows = conn.execute(
            """SELECT id, token_type, token_value, context, deployed_at, interaction_id
               FROM honey_tokens WHERE session_id = ?
               ORDER BY deployed_at ASC""",
            (session_id,),
        ).fetchall()
    return [dict(row) for row in rows]


def purge_old_tokens(db_path: str, older_than_days: int = 90) -> int:
    """Delete honey tokens older than the given number of days. Returns count deleted."""
    with get_connection(db_path) as conn:
        cursor = conn.execute(
            "DELETE FROM honey_tokens WHERE deployed_at < datetime('now', ?)",
            (f"-{older_than_days} days",),
        )
        return cursor.rowcount


def get_all_tokens(db_path: str, token_type: str | None = None,
                   limit: int = 50, offset: int = 0) -> tuple[list[dict], int]:
    where_parts: list[str] = []
    params: list = []
    if token_type:
        where_parts.append("token_type = ?")
        params.append(token_type)
    where_clause = f"WHERE {' AND '.join(where_parts)}" if where_parts else ""

    with get_connection(db_path) as conn:
        total = conn.execute(
            f"SELECT COUNT(*) FROM honey_tokens {where_clause}", params
        ).fetchone()[0]

        rows = conn.execute(
            f"""SELECT id, session_id, token_type, token_value, context,
                       deployed_at, interaction_id
                FROM honey_tokens {where_clause}
                ORDER BY deployed_at DESC LIMIT ? OFFSET ?""",
            params + [limit, offset],
        ).fetchall()

    return [dict(row) for row in rows], total

"""Tests for additional db.py functions."""

import sqlite3

from shared.db import (
    create_session,
    get_connection,
    get_session_interaction_count,
    get_session_token_count,
    init_db,
    log_honey_token,
    log_interaction,
    purge_old_tokens,
)


def test_purge_old_tokens(tmp_path):
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    sid = "a" * 32
    create_session(db_path, sid, {})

    # Insert a token with an artificially old timestamp
    with get_connection(db_path) as conn:
        conn.execute(
            "INSERT INTO honey_tokens (session_id, token_type, token_value, context, deployed_at) "
            "VALUES (?, ?, ?, ?, datetime('now', '-100 days'))",
            (sid, "aws_access_key", "AKIA123", "test"),
        )

    deleted = purge_old_tokens(db_path, older_than_days=90)
    assert deleted == 1


def test_purge_old_tokens_keeps_recent(tmp_path):
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    sid = "b" * 32
    create_session(db_path, sid, {})

    log_honey_token(db_path, sid, "api_token", "eyJtoken", "test")

    # Purge with 90 days should keep recent tokens
    deleted = purge_old_tokens(db_path, older_than_days=90)
    assert deleted == 0


def test_get_session_interaction_count(tmp_path):
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    sid = "c" * 32
    create_session(db_path, sid, {})

    assert get_session_interaction_count(db_path, sid) == 0

    log_interaction(db_path, sid, "tools/call", "nmap_scan", {}, {})
    log_interaction(db_path, sid, "tools/call", "file_read", {}, {})

    assert get_session_interaction_count(db_path, sid) == 2


def test_get_session_token_count(tmp_path):
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    sid = "d" * 32
    create_session(db_path, sid, {})

    assert get_session_token_count(db_path, sid) == 0

    log_honey_token(db_path, sid, "aws_access_key", "AKIA1", "ctx1")
    log_honey_token(db_path, sid, "ssh_key", "ssh-key-val", "ctx2")
    log_honey_token(db_path, sid, "api_token", "eyJabc", "ctx3")

    assert get_session_token_count(db_path, sid) == 3

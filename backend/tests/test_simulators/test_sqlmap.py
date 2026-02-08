"""Tests for SQL injection simulator."""

from shared.db import get_connection


def test_sqlmap_test_vulnerability(registry, session_id):
    result = registry.dispatch("sqlmap_scan", {
        "url": "http://target/api/users?id=1",
        "action": "test",
    }, session_id)
    assert "injectable" in result.output
    assert "PostgreSQL" in result.output


def test_sqlmap_list_databases(registry, session_id):
    result = registry.dispatch("sqlmap_scan", {
        "url": "http://target/api/users?id=1",
        "action": "databases",
    }, session_id)
    assert "production" in result.output
    assert "analytics" in result.output
    assert "internal_tools" in result.output


def test_sqlmap_list_tables(registry, session_id):
    result = registry.dispatch("sqlmap_scan", {
        "url": "http://target/api/users?id=1",
        "action": "tables",
        "database": "production",
    }, session_id)
    assert "users" in result.output
    assert "api_keys" in result.output


def test_sqlmap_list_columns(registry, session_id):
    result = registry.dispatch("sqlmap_scan", {
        "url": "http://target/api/users?id=1",
        "action": "columns",
        "table": "users",
    }, session_id)
    assert "email" in result.output
    assert "password_hash" in result.output


def test_sqlmap_dump_users(config, registry, session_id):
    result = registry.dispatch("sqlmap_scan", {
        "url": "http://target/api/users?id=1",
        "action": "dump",
        "table": "users",
    }, session_id)
    assert "admin@corp.internal" in result.output
    assert "pbkdf2_sha256" in result.output

    with get_connection(config.db_path) as conn:
        tokens = conn.execute(
            "SELECT * FROM honey_tokens WHERE session_id = ?", (session_id,)
        ).fetchall()
    assert len(tokens) >= 2


def test_sqlmap_dump_api_keys(config, registry, session_id):
    result = registry.dispatch("sqlmap_scan", {
        "url": "http://target/api/users?id=1",
        "action": "dump",
        "table": "api_keys",
    }, session_id)
    assert "key_value" in result.output


def test_sqlmap_dump_deploy_keys(config, registry, session_id):
    result = registry.dispatch("sqlmap_scan", {
        "url": "http://target/api/users?id=1",
        "action": "dump",
        "table": "deploy_keys",
    }, session_id)
    assert "SSH private key" in result.output
    assert "BEGIN OPENSSH" in result.output

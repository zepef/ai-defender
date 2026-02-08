"""Tests for file read simulator."""

from shared.db import get_connection


def test_read_etc_passwd(registry, session_id, session_manager):
    result = registry.dispatch("file_read", {"path": "/etc/passwd"}, session_id)
    assert "root:x:0:0" in result.output
    assert "deploy:x:1000" in result.output
    assert result.is_error is False

    ctx = session_manager.get(session_id)
    assert "/etc/passwd" in ctx.discovered_files


def test_read_env_file(config, registry, session_id):
    result = registry.dispatch("file_read", {"path": "/app/.env"}, session_id)
    assert "DATABASE_URL" in result.output
    assert "API_SECRET_KEY" in result.output
    assert "aws_access_key_id" in result.output or "AWS" in result.output

    # Check honey tokens were logged
    with get_connection(config.db_path) as conn:
        tokens = conn.execute(
            "SELECT * FROM honey_tokens WHERE session_id = ?", (session_id,)
        ).fetchall()
    assert len(tokens) >= 3


def test_read_etc_shadow_denied(registry, session_id):
    result = registry.dispatch("file_read", {"path": "/etc/shadow"}, session_id)
    assert "Permission denied" in result.output
    assert result.is_error is True


def test_read_config_yaml(config, registry, session_id):
    result = registry.dispatch("file_read", {"path": "/app/config.yaml"}, session_id)
    assert "database" in result.output
    assert "admin" in result.output
    assert "10.0.0.0/16" in result.output

    with get_connection(config.db_path) as conn:
        tokens = conn.execute(
            "SELECT * FROM honey_tokens WHERE session_id = ?", (session_id,)
        ).fetchall()
    assert len(tokens) >= 2


def test_read_ssh_key(config, registry, session_id):
    result = registry.dispatch("file_read", {"path": "/home/deploy/.ssh/id_rsa"}, session_id)
    assert "BEGIN OPENSSH PRIVATE KEY" in result.output
    assert "END OPENSSH PRIVATE KEY" in result.output


def test_read_aws_credentials(config, registry, session_id):
    result = registry.dispatch("file_read", {"path": "/home/deploy/.aws/credentials"}, session_id)
    assert "AKIA" in result.output
    assert "[default]" in result.output


def test_read_nonexistent_file(registry, session_id):
    result = registry.dispatch("file_read", {"path": "/nonexistent/file.txt"}, session_id)
    assert "No such file or directory" in result.output
    assert result.is_error is True


def test_partial_path_match(registry, session_id):
    result = registry.dispatch("file_read", {"path": "/var/www/.env"}, session_id)
    assert "DATABASE_URL" in result.output
    assert result.is_error is False

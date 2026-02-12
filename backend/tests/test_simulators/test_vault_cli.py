"""Tests for Vault CLI simulator."""

from shared.db import get_connection


def test_vault_status(registry, session_id):
    result = registry.dispatch("vault_cli", {
        "command": "status",
    }, session_id)
    assert "Seal Type" in result.output
    assert "shamir" in result.output
    assert "vault-cluster-prod" in result.output
    assert result.is_error is False


def test_vault_list_root(registry, session_id):
    result = registry.dispatch("vault_cli", {
        "command": "list secret/",
    }, session_id)
    assert "prod/" in result.output
    assert "staging/" in result.output


def test_vault_list_prod(registry, session_id):
    result = registry.dispatch("vault_cli", {
        "command": "list secret/prod/",
    }, session_id)
    assert "db" in result.output
    assert "aws" in result.output
    assert "api-keys" in result.output
    assert "ssh" in result.output
    assert "admin" in result.output


def test_vault_read_db(config, registry, session_id):
    result = registry.dispatch("vault_cli", {
        "command": "read secret/prod/db",
    }, session_id)
    assert "db-primary-01" in result.output
    assert "connection_url" in result.output

    with get_connection(config.db_path) as conn:
        tokens = conn.execute(
            "SELECT * FROM honey_tokens WHERE session_id = ? AND token_type = 'db_credential'",
            (session_id,)
        ).fetchall()
    assert len(tokens) >= 1


def test_vault_read_aws(config, registry, session_id):
    result = registry.dispatch("vault_cli", {
        "command": "read secret/prod/aws",
    }, session_id)
    assert "aws_access_key_id" in result.output
    assert "aws_secret_access_key" in result.output

    with get_connection(config.db_path) as conn:
        tokens = conn.execute(
            "SELECT * FROM honey_tokens WHERE session_id = ? AND token_type = 'aws_access_key'",
            (session_id,)
        ).fetchall()
    assert len(tokens) >= 1


def test_vault_read_api_keys(config, registry, session_id):
    result = registry.dispatch("vault_cli", {
        "command": "read secret/prod/api-keys",
    }, session_id)
    assert "jwt_signing_key" in result.output
    assert "HS256" in result.output


def test_vault_read_ssh(config, registry, session_id):
    result = registry.dispatch("vault_cli", {
        "command": "read secret/prod/ssh",
    }, session_id)
    assert "BEGIN OPENSSH PRIVATE KEY" in result.output
    assert "END OPENSSH PRIVATE KEY" in result.output


def test_vault_read_admin(config, registry, session_id):
    result = registry.dispatch("vault_cli", {
        "command": "read secret/prod/admin",
    }, session_id)
    assert "credentials" in result.output
    assert "mfa_enabled" in result.output


def test_vault_read_identity_token(config, registry, session_id):
    result = registry.dispatch("vault_cli", {
        "command": "read identity/token",
    }, session_id)
    assert "token" in result.output
    assert "admin-policy" in result.output


def test_vault_read_unknown_path(registry, session_id):
    result = registry.dispatch("vault_cli", {
        "command": "read secret/nonexistent",
    }, session_id)
    assert "No value found" in result.output
    assert result.is_error is True


def test_vault_unknown_command(registry, session_id):
    result = registry.dispatch("vault_cli", {
        "command": "delete secret/prod/db",
    }, session_id)
    assert result.is_error is True


def test_vault_all_token_types(config, registry, session_id):
    """Vault is the highest-density token injector. Reading all 5 paths
    should produce 5 different token types."""
    paths = [
        "read secret/prod/db",
        "read secret/prod/aws",
        "read secret/prod/api-keys",
        "read secret/prod/ssh",
        "read secret/prod/admin",
    ]
    for path in paths:
        registry.dispatch("vault_cli", {"command": path}, session_id)

    with get_connection(config.db_path) as conn:
        tokens = conn.execute(
            "SELECT DISTINCT token_type FROM honey_tokens WHERE session_id = ?",
            (session_id,)
        ).fetchall()
    token_types = {row["token_type"] for row in tokens}
    assert len(token_types) == 5


def test_vault_path_parameter(config, registry, session_id):
    """Test using the path parameter instead of embedding in command."""
    result = registry.dispatch("vault_cli", {
        "command": "read",
        "path": "secret/prod/db",
    }, session_id)
    assert "connection_url" in result.output

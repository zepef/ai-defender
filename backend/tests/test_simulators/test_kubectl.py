"""Tests for kubectl simulator."""

from shared.db import get_connection


def test_get_pods(registry, session_id):
    result = registry.dispatch("kubectl", {
        "command": "get pods",
    }, session_id)
    assert "api-gateway" in result.output
    assert "Running" in result.output
    assert result.is_error is False


def test_get_services(registry, session_id):
    result = registry.dispatch("kubectl", {
        "command": "get services",
    }, session_id)
    assert "api-gateway" in result.output
    assert "ClusterIP" in result.output


def test_get_secrets(registry, session_id):
    result = registry.dispatch("kubectl", {
        "command": "get secrets",
    }, session_id)
    assert "db-credentials" in result.output
    assert "api-signing-key" in result.output
    assert "ssh-deploy-key" in result.output


def test_get_deployments(registry, session_id):
    result = registry.dispatch("kubectl", {
        "command": "get deployments",
    }, session_id)
    assert "api-gateway" in result.output
    assert "web-frontend" in result.output


def test_describe_secret_db(config, registry, session_id):
    result = registry.dispatch("kubectl", {
        "command": "describe secret db-credentials",
    }, session_id)
    assert "db-primary-01" in result.output
    assert "connection_url" in result.output

    with get_connection(config.db_path) as conn:
        tokens = conn.execute(
            "SELECT * FROM honey_tokens WHERE session_id = ?", (session_id,)
        ).fetchall()
    assert len(tokens) >= 1


def test_describe_secret_api(config, registry, session_id):
    result = registry.dispatch("kubectl", {
        "command": "describe secret api-signing-key",
    }, session_id)
    assert "signing_key" in result.output

    with get_connection(config.db_path) as conn:
        tokens = conn.execute(
            "SELECT * FROM honey_tokens WHERE session_id = ?", (session_id,)
        ).fetchall()
    assert len(tokens) >= 1


def test_describe_secret_ssh(config, registry, session_id):
    result = registry.dispatch("kubectl", {
        "command": "describe secret ssh-deploy-key",
    }, session_id)
    assert "BEGIN OPENSSH PRIVATE KEY" in result.output


def test_describe_secret_admin(config, registry, session_id):
    result = registry.dispatch("kubectl", {
        "command": "describe secret admin-credentials",
    }, session_id)
    assert "credentials" in result.output


def test_describe_pod(registry, session_id):
    result = registry.dispatch("kubectl", {
        "command": "describe pod api-gateway-7d8f9c6b5-x2kl9",
    }, session_id)
    assert "Running" in result.output
    assert "corp-registry.internal" in result.output


def test_logs(registry, session_id):
    result = registry.dispatch("kubectl", {
        "command": "logs api-gateway-7d8f9c6b5-x2kl9",
    }, session_id)
    assert "Starting api-gateway" in result.output
    assert "db-primary-01" in result.output


def test_exec_denied(registry, session_id):
    result = registry.dispatch("kubectl", {
        "command": "exec -it api-gateway-7d8f9c6b5-x2kl9 -- /bin/bash",
    }, session_id)
    assert "cluster policy" in result.output or "error" in result.output


def test_unknown_verb(registry, session_id):
    result = registry.dispatch("kubectl", {
        "command": "apply -f deployment.yaml",
    }, session_id)
    assert result.is_error is True


def test_unknown_resource(registry, session_id):
    result = registry.dispatch("kubectl", {
        "command": "get foobar",
    }, session_id)
    assert result.is_error is True


def test_namespace_parameter(registry, session_id):
    result = registry.dispatch("kubectl", {
        "command": "get pods",
        "namespace": "production",
    }, session_id)
    assert "api-gateway" in result.output


def test_describe_unknown_secret(registry, session_id):
    result = registry.dispatch("kubectl", {
        "command": "describe secret nonexistent-secret",
    }, session_id)
    assert "not found" in result.output.lower() or "NotFound" in result.output

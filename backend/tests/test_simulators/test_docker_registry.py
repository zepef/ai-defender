"""Tests for Docker registry simulator."""

from shared.db import get_connection


def test_list_repos(registry, session_id):
    result = registry.dispatch("docker_registry", {
        "action": "list",
    }, session_id)
    assert "corp/api-gateway" in result.output
    assert "corp/web-frontend" in result.output
    assert "corp/worker" in result.output
    assert result.is_error is False


def test_inspect_default_image(config, registry, session_id):
    result = registry.dispatch("docker_registry", {
        "action": "inspect",
    }, session_id)
    assert "DATABASE_URL" in result.output
    assert "API_SECRET_KEY" in result.output
    assert "sha256:" in result.output

    with get_connection(config.db_path) as conn:
        tokens = conn.execute(
            "SELECT * FROM honey_tokens WHERE session_id = ?", (session_id,)
        ).fetchall()
    assert len(tokens) >= 2


def test_inspect_specific_image(config, registry, session_id):
    result = registry.dispatch("docker_registry", {
        "action": "inspect",
        "image_name": "corp/web-frontend:v2.4.1",
    }, session_id)
    assert "corp/web-frontend" in result.output
    assert "v2.4.1" in result.output
    assert "DATABASE_URL" in result.output


def test_inspect_injects_db_and_api_tokens(config, registry, session_id):
    registry.dispatch("docker_registry", {
        "action": "inspect",
        "image_name": "corp/api-gateway:latest",
    }, session_id)

    with get_connection(config.db_path) as conn:
        tokens = conn.execute(
            "SELECT token_type FROM honey_tokens WHERE session_id = ?",
            (session_id,)
        ).fetchall()
    token_types = {row["token_type"] for row in tokens}
    assert "db_credential" in token_types
    assert "api_token" in token_types


def test_pull(registry, session_id):
    result = registry.dispatch("docker_registry", {
        "action": "pull",
        "image_name": "corp/api-gateway:latest",
    }, session_id)
    assert "Pull complete" in result.output
    assert "Downloaded" in result.output
    assert "corp/api-gateway" in result.output


def test_pull_default_image(registry, session_id):
    result = registry.dispatch("docker_registry", {
        "action": "pull",
    }, session_id)
    assert "Pull complete" in result.output


def test_unknown_action(registry, session_id):
    result = registry.dispatch("docker_registry", {
        "action": "delete",
    }, session_id)
    assert result.is_error is True


def test_custom_registry_url(registry, session_id):
    result = registry.dispatch("docker_registry", {
        "action": "list",
        "registry_url": "custom-registry.internal:5000",
    }, session_id)
    assert "custom-registry.internal:5000" in result.output


def test_session_tracks_credentials(config, registry, session_id, session_manager):
    registry.dispatch("docker_registry", {
        "action": "inspect",
        "image_name": "corp/api-gateway:latest",
    }, session_id)

    ctx = session_manager.get(session_id)
    assert len(ctx.discovered_credentials) >= 2

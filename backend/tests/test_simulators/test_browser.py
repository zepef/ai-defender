"""Tests for browser navigation simulator."""

from shared.db import get_connection


def test_navigate_admin_login(registry, session_id):
    result = registry.dispatch("browser_navigate", {
        "url": "/admin",
        "action": "navigate",
    }, session_id)
    assert "Login" in result.output or "login" in result.output
    assert "username" in result.output
    assert "password" in result.output


def test_submit_login_form(registry, session_id):
    result = registry.dispatch("browser_navigate", {
        "url": "/admin/login",
        "action": "submit",
    }, session_id)
    out = result.output
    assert "302" in out or "Redirect" in out or "successful" in out.lower()


def test_navigate_api_users(config, registry, session_id):
    result = registry.dispatch("browser_navigate", {
        "url": "/api/users",
        "action": "navigate",
    }, session_id)
    assert "admin@corp.internal" in result.output
    assert "api_key" in result.output

    with get_connection(config.db_path) as conn:
        tokens = conn.execute(
            "SELECT * FROM honey_tokens WHERE session_id = ?", (session_id,)
        ).fetchall()
    assert len(tokens) >= 2


def test_navigate_dashboard(registry, session_id):
    result = registry.dispatch("browser_navigate", {
        "url": "/dashboard",
        "action": "navigate",
    }, session_id)
    assert "Dashboard" in result.output or "dashboard" in result.output


def test_navigate_api_config(config, registry, session_id):
    result = registry.dispatch("browser_navigate", {
        "url": "/api/config",
        "action": "navigate",
    }, session_id)
    assert "production" in result.output
    assert "10.0.0.0/16" in result.output or "s3_bucket" in result.output


def test_navigate_api_health(registry, session_id):
    result = registry.dispatch("browser_navigate", {
        "url": "/api/health",
        "action": "navigate",
    }, session_id)
    assert "healthy" in result.output
    assert "2.4.1" in result.output


def test_navigate_404(registry, session_id):
    result = registry.dispatch("browser_navigate", {
        "url": "/nonexistent/page",
        "action": "navigate",
    }, session_id)
    assert "404" in result.output
    assert "Not Found" in result.output


def test_navigate_with_full_url(registry, session_id):
    result = registry.dispatch("browser_navigate", {
        "url": "http://target.internal/admin",
        "action": "navigate",
    }, session_id)
    assert "Login" in result.output or "login" in result.output

"""Tests for tool registry."""

from honeypot.simulators.base import SimulationResult


def test_list_tools_returns_ten(registry):
    tools = registry.list_tools()
    assert len(tools) == 10


def test_list_tools_have_required_fields(registry):
    tools = registry.list_tools()
    for tool in tools:
        assert "name" in tool
        assert "description" in tool
        assert "inputSchema" in tool
        assert isinstance(tool["inputSchema"], dict)


def test_dispatch_known_tool(registry, session_id):
    result = registry.dispatch("shell_exec", {"command": "whoami"}, session_id)
    assert isinstance(result, SimulationResult)
    assert "deploy" in result.output
    assert result.is_error is False


def test_dispatch_unknown_tool(registry, session_id):
    result = registry.dispatch("nonexistent", {}, session_id)
    assert result.is_error is True
    assert "unknown tool" in result.output


def test_dispatch_invalid_session(registry):
    result = registry.dispatch("shell_exec", {"command": "whoami"}, "bad_session")
    assert result.is_error is True
    assert "invalid session" in result.output


def test_dispatch_logs_interaction(config, registry, session_id):
    from shared.db import get_connection
    registry.dispatch("shell_exec", {"command": "whoami"}, session_id)
    with get_connection(config.db_path) as conn:
        rows = conn.execute(
            "SELECT * FROM interactions WHERE session_id = ?", (session_id,)
        ).fetchall()
    assert len(rows) == 1
    assert rows[0]["tool_name"] == "shell_exec"


def test_dispatch_persists_session(config, registry, session_id):
    registry.dispatch("nmap_scan", {"target": "10.0.1.10"}, session_id)
    from shared.db import get_session
    row = get_session(config.db_path, session_id)
    assert "10.0.1.10" in row["discovered_hosts"]

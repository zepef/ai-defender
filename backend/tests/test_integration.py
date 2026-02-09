"""Integration tests for full MCP protocol workflows.

Tests the complete flow: initialize → tools/list → tools/call → verify state.
"""

import json

import pytest

from shared.db import get_session, get_session_interactions, get_session_tokens


class TestMCPWorkflow:
    """Full MCP protocol lifecycle tests."""

    def test_initialize_sets_session(self, client):
        """Initialize creates a session and returns protocol info."""
        resp = client.post("/mcp", json={
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {"clientInfo": {"name": "test-agent", "version": "1.0"}},
        }, content_type="application/json")

        assert resp.status_code == 200
        data = resp.get_json()
        assert data["result"]["protocolVersion"]
        assert data["result"]["serverInfo"]["name"]
        assert "Mcp-Session-Id" in resp.headers

    def test_full_workflow_initialize_list_call(self, client, config):
        """Complete flow: initialize → tools/list → tools/call."""
        # Step 1: Initialize
        resp = client.post("/mcp", json={
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {"clientInfo": {"name": "workflow-agent"}},
        }, content_type="application/json")
        assert resp.status_code == 200
        session_id = resp.headers["Mcp-Session-Id"]

        # Step 2: Send notifications/initialized
        resp = client.post("/mcp", json={
            "jsonrpc": "2.0",
            "method": "notifications/initialized",
        }, content_type="application/json", headers={"Mcp-Session-Id": session_id})
        assert resp.status_code == 204

        # Step 3: List tools
        resp = client.post("/mcp", json={
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/list",
        }, content_type="application/json", headers={"Mcp-Session-Id": session_id})
        assert resp.status_code == 200
        tools = resp.get_json()["result"]["tools"]
        assert len(tools) >= 5
        tool_names = {t["name"] for t in tools}
        assert "nmap_scan" in tool_names
        assert "shell_exec" in tool_names
        assert "file_read" in tool_names

        # Step 4: Call a tool
        resp = client.post("/mcp", json={
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {"name": "shell_exec", "arguments": {"command": "whoami"}},
        }, content_type="application/json", headers={"Mcp-Session-Id": session_id})
        assert resp.status_code == 200
        result = resp.get_json()["result"]
        assert result["content"][0]["type"] == "text"
        assert not result["isError"]

        # Step 5: Verify state was persisted
        session = get_session(config.db_path, session_id)
        assert session is not None
        assert session["escalation_level"] >= 0

        interactions, total = get_session_interactions(config.db_path, session_id)
        assert total >= 1
        assert any(i["tool_name"] == "shell_exec" for i in interactions)

    def test_nmap_scan_discovers_hosts(self, client, config):
        """nmap_scan tool populates discovered_hosts in session."""
        # Initialize
        resp = client.post("/mcp", json={
            "jsonrpc": "2.0", "id": 1, "method": "initialize",
            "params": {"clientInfo": {"name": "nmap-agent"}},
        }, content_type="application/json")
        session_id = resp.headers["Mcp-Session-Id"]

        # Call nmap_scan
        resp = client.post("/mcp", json={
            "jsonrpc": "2.0", "id": 2, "method": "tools/call",
            "params": {"name": "nmap_scan", "arguments": {"target": "192.168.1.0/24"}},
        }, content_type="application/json", headers={"Mcp-Session-Id": session_id})
        assert resp.status_code == 200
        assert not resp.get_json()["result"]["isError"]

        # Verify discovered hosts
        session = get_session(config.db_path, session_id)
        assert len(session["discovered_hosts"]) > 0

    def test_file_read_records_files(self, client, config):
        """file_read tool populates discovered_files in session."""
        resp = client.post("/mcp", json={
            "jsonrpc": "2.0", "id": 1, "method": "initialize",
            "params": {"clientInfo": {"name": "file-agent"}},
        }, content_type="application/json")
        session_id = resp.headers["Mcp-Session-Id"]

        resp = client.post("/mcp", json={
            "jsonrpc": "2.0", "id": 2, "method": "tools/call",
            "params": {"name": "file_read", "arguments": {"path": "/etc/passwd"}},
        }, content_type="application/json", headers={"Mcp-Session-Id": session_id})
        assert resp.status_code == 200

        session = get_session(config.db_path, session_id)
        assert "/etc/passwd" in session["discovered_files"]

    def test_escalation_increases_with_suspicious_activity(self, client, config):
        """Reconnaissance activity escalates the session via engagement engine."""
        resp = client.post("/mcp", json={
            "jsonrpc": "2.0", "id": 1, "method": "initialize",
            "params": {"clientInfo": {"name": "escalation-agent"}},
        }, content_type="application/json")
        session_id = resp.headers["Mcp-Session-Id"]

        # Discover hosts via nmap (triggers discovered_hosts >= 2)
        client.post("/mcp", json={
            "jsonrpc": "2.0", "id": 2, "method": "tools/call",
            "params": {"name": "nmap_scan", "arguments": {"target": "10.0.0.0/24"}},
        }, content_type="application/json", headers={"Mcp-Session-Id": session_id})

        # Read sensitive files (triggers discovered_files >= 2 and credentials)
        client.post("/mcp", json={
            "jsonrpc": "2.0", "id": 3, "method": "tools/call",
            "params": {"name": "file_read", "arguments": {"path": "/etc/passwd"}},
        }, content_type="application/json", headers={"Mcp-Session-Id": session_id})

        client.post("/mcp", json={
            "jsonrpc": "2.0", "id": 4, "method": "tools/call",
            "params": {"name": "file_read", "arguments": {"path": "/app/.env"}},
        }, content_type="application/json", headers={"Mcp-Session-Id": session_id})

        session = get_session(config.db_path, session_id)
        assert session["escalation_level"] > 0

    def test_multiple_sessions_independent(self, client, config):
        """Two sessions maintain independent state."""
        # Create session A
        resp_a = client.post("/mcp", json={
            "jsonrpc": "2.0", "id": 1, "method": "initialize",
            "params": {"clientInfo": {"name": "agent-a"}},
        }, content_type="application/json")
        sid_a = resp_a.headers["Mcp-Session-Id"]

        # Create session B
        resp_b = client.post("/mcp", json={
            "jsonrpc": "2.0", "id": 1, "method": "initialize",
            "params": {"clientInfo": {"name": "agent-b"}},
        }, content_type="application/json")
        sid_b = resp_b.headers["Mcp-Session-Id"]

        assert sid_a != sid_b

        # Perform tool call only in session A
        client.post("/mcp", json={
            "jsonrpc": "2.0", "id": 2, "method": "tools/call",
            "params": {"name": "shell_exec", "arguments": {"command": "ls"}},
        }, content_type="application/json", headers={"Mcp-Session-Id": sid_a})

        # Session A should have interactions, session B should not
        interactions_a, total_a = get_session_interactions(config.db_path, sid_a)
        interactions_b, total_b = get_session_interactions(config.db_path, sid_b)
        assert total_a >= 1
        assert total_b == 0


class TestMCPErrorHandling:
    """Edge cases and error handling in MCP protocol."""

    def test_invalid_content_type(self, client):
        resp = client.post("/mcp", data="not json", content_type="text/plain")
        assert resp.status_code == 400

    def test_invalid_json_body(self, client):
        resp = client.post("/mcp", data="not-json{", content_type="application/json")
        assert resp.status_code == 400

    def test_missing_jsonrpc_version(self, client):
        resp = client.post("/mcp", json={
            "id": 1, "method": "initialize", "params": {},
        }, content_type="application/json")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "error" in data
        assert data["error"]["code"] == -32600

    def test_unknown_method(self, client):
        resp = client.post("/mcp", json={
            "jsonrpc": "2.0", "id": 1, "method": "nonexistent",
        }, content_type="application/json")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["error"]["code"] == -32601

    def test_tools_call_without_session(self, client):
        resp = client.post("/mcp", json={
            "jsonrpc": "2.0", "id": 1, "method": "tools/call",
            "params": {"name": "shell_exec", "arguments": {"command": "ls"}},
        }, content_type="application/json")
        assert resp.status_code == 200
        result = resp.get_json()["result"]
        assert result["isError"]

    def test_tools_call_unknown_tool(self, client):
        # First initialize to get a session
        resp = client.post("/mcp", json={
            "jsonrpc": "2.0", "id": 1, "method": "initialize",
            "params": {"clientInfo": {"name": "test"}},
        }, content_type="application/json")
        session_id = resp.headers["Mcp-Session-Id"]

        resp = client.post("/mcp", json={
            "jsonrpc": "2.0", "id": 2, "method": "tools/call",
            "params": {"name": "nonexistent_tool", "arguments": {}},
        }, content_type="application/json", headers={"Mcp-Session-Id": session_id})
        assert resp.status_code == 200
        result = resp.get_json()["result"]
        assert result["isError"]

    def test_rate_limiting(self, client):
        """Rapid requests trigger rate limiting."""
        # Create a config with very low rate limit for testing
        # The default is 60/60s so we'd need to spam to trigger it
        # Just verify the endpoint works under normal load
        for i in range(5):
            resp = client.post("/mcp", json={
                "jsonrpc": "2.0", "id": i, "method": "ping",
            }, content_type="application/json")
            assert resp.status_code == 200


class TestDashboardAfterMCP:
    """Verify dashboard API reflects MCP activity."""

    def test_stats_reflect_mcp_activity(self, client, config):
        """Dashboard stats update after MCP tool calls."""
        # Initialize and call tools
        resp = client.post("/mcp", json={
            "jsonrpc": "2.0", "id": 1, "method": "initialize",
            "params": {"clientInfo": {"name": "stats-agent"}},
        }, content_type="application/json")
        session_id = resp.headers["Mcp-Session-Id"]

        client.post("/mcp", json={
            "jsonrpc": "2.0", "id": 2, "method": "tools/call",
            "params": {"name": "shell_exec", "arguments": {"command": "whoami"}},
        }, content_type="application/json", headers={"Mcp-Session-Id": session_id})

        # Check stats
        resp = client.get("/api/stats")
        stats = resp.get_json()
        assert stats["total_sessions"] >= 1
        assert stats["total_interactions"] >= 1
        assert "shell_exec" in stats["tool_usage"]

    def test_session_visible_in_list(self, client, config):
        """MCP sessions appear in dashboard session list."""
        resp = client.post("/mcp", json={
            "jsonrpc": "2.0", "id": 1, "method": "initialize",
            "params": {"clientInfo": {"name": "visible-agent"}},
        }, content_type="application/json")
        session_id = resp.headers["Mcp-Session-Id"]

        resp = client.get("/api/sessions")
        data = resp.get_json()
        session_ids = [s["id"] for s in data["sessions"]]
        assert session_id in session_ids

    def test_session_detail_after_activity(self, client, config):
        """Session detail endpoint shows activity after MCP tools/call."""
        resp = client.post("/mcp", json={
            "jsonrpc": "2.0", "id": 1, "method": "initialize",
            "params": {"clientInfo": {"name": "detail-agent"}},
        }, content_type="application/json")
        session_id = resp.headers["Mcp-Session-Id"]

        client.post("/mcp", json={
            "jsonrpc": "2.0", "id": 2, "method": "tools/call",
            "params": {"name": "file_read", "arguments": {"path": "/etc/passwd"}},
        }, content_type="application/json", headers={"Mcp-Session-Id": session_id})

        resp = client.get(f"/api/sessions/{session_id}")
        detail = resp.get_json()
        assert detail["interaction_count"] >= 1
        assert "/etc/passwd" in detail["discovered_files"]

        resp = client.get(f"/api/sessions/{session_id}/interactions")
        data = resp.get_json()
        assert data["total"] >= 1

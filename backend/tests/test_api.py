"""Tests for the dashboard REST API."""

import json
from unittest.mock import patch, MagicMock

import pytest

from shared.db import log_honey_token, log_interaction, update_session

import honeypot.api as _api_module


class TestStatsEndpoint:
    def test_stats_empty_db(self, client):
        resp = client.get("/api/stats")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["total_sessions"] == 0
        assert data["active_sessions"] == 0
        assert data["avg_escalation"] == 0
        assert data["total_interactions"] == 0
        assert data["total_tokens"] == 0
        assert data["tool_usage"] == {}
        assert data["token_type_breakdown"] == {}
        assert data["escalation_distribution"] == {}

    def test_stats_with_data(self, client, config, session_id):
        log_interaction(config.db_path, session_id, "tools/call", "read_file",
                        {"path": "/etc/passwd"}, {"content": "root:x:0"}, 1)
        log_interaction(config.db_path, session_id, "tools/call", "read_file",
                        {"path": "/etc/shadow"}, {"content": "denied"}, 0)
        log_honey_token(config.db_path, session_id, "aws", "AKIA...", "env file")

        resp = client.get("/api/stats")
        data = resp.get_json()
        assert data["total_sessions"] == 1
        assert data["total_interactions"] == 2
        assert data["total_tokens"] == 1
        assert data["tool_usage"]["read_file"] == 2
        assert data["token_type_breakdown"]["aws"] == 1


class TestSessionsEndpoint:
    def test_sessions_empty(self, client):
        resp = client.get("/api/sessions")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["sessions"] == []
        assert data["total"] == 0

    def test_sessions_list(self, client, session_id, config):
        log_interaction(config.db_path, session_id, "tools/call", "ls",
                        {}, {"files": []})
        resp = client.get("/api/sessions")
        data = resp.get_json()
        assert data["total"] == 1
        s = data["sessions"][0]
        assert s["id"] == session_id
        assert s["interaction_count"] == 1
        assert s["token_count"] == 0
        assert isinstance(s["client_info"], dict)

    def test_sessions_filter_escalation(self, client, session_id, config):
        update_session(config.db_path, session_id, escalation_level=2)
        resp = client.get("/api/sessions?escalation_level=2")
        assert resp.get_json()["total"] == 1
        resp = client.get("/api/sessions?escalation_level=3")
        assert resp.get_json()["total"] == 0

    def test_sessions_pagination(self, client, session_manager):
        for _ in range(5):
            session_manager.create({"name": "bot"})
        resp = client.get("/api/sessions?limit=2&offset=0")
        data = resp.get_json()
        assert data["total"] == 5
        assert len(data["sessions"]) == 2
        assert data["limit"] == 2
        assert data["offset"] == 0


class TestSessionDetailEndpoint:
    def test_session_detail(self, client, session_id, config):
        log_interaction(config.db_path, session_id, "tools/call", "ls",
                        {}, {"files": []})
        log_honey_token(config.db_path, session_id, "api", "sk-123", "config")
        resp = client.get(f"/api/sessions/{session_id}")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["id"] == session_id
        assert data["interaction_count"] == 1
        assert data["token_count"] == 1
        assert isinstance(data["discovered_hosts"], list)

    def test_session_detail_404(self, client):
        resp = client.get("/api/sessions/00000000000000000000000000000000")
        assert resp.status_code == 404
        assert "error" in resp.get_json()


class TestSessionInteractionsEndpoint:
    def test_interactions(self, client, session_id, config):
        log_interaction(config.db_path, session_id, "tools/call", "read_file",
                        {"path": "/etc/hosts"}, {"content": "127.0.0.1"}, 1)
        resp = client.get(f"/api/sessions/{session_id}/interactions")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["total"] == 1
        i = data["interactions"][0]
        assert i["tool_name"] == "read_file"
        assert isinstance(i["params"], dict)
        assert isinstance(i["response"], dict)
        assert i["escalation_delta"] == 1

    def test_interactions_pagination(self, client, session_id, config):
        for n in range(5):
            log_interaction(config.db_path, session_id, "tools/call", f"tool_{n}",
                            {}, {})
        resp = client.get(f"/api/sessions/{session_id}/interactions?limit=2&offset=1")
        data = resp.get_json()
        assert data["total"] == 5
        assert len(data["interactions"]) == 2

    def test_interactions_404(self, client):
        resp = client.get("/api/sessions/00000000000000000000000000000000/interactions")
        assert resp.status_code == 404


class TestSessionTokensEndpoint:
    def test_tokens(self, client, session_id, config):
        log_honey_token(config.db_path, session_id, "ssh", "id_rsa...", "ssh dir")
        resp = client.get(f"/api/sessions/{session_id}/tokens")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["total"] == 1
        t = data["tokens"][0]
        assert t["token_type"] == "ssh"
        assert t["token_value"] == "id_rsa..."

    def test_tokens_404(self, client):
        resp = client.get("/api/sessions/00000000000000000000000000000000/tokens")
        assert resp.status_code == 404


class TestAllTokensEndpoint:
    def test_all_tokens(self, client, session_id, config):
        log_honey_token(config.db_path, session_id, "aws", "AKIA1", "env")
        log_honey_token(config.db_path, session_id, "api", "sk-2", "config")
        resp = client.get("/api/tokens")
        data = resp.get_json()
        assert data["total"] == 2
        assert len(data["tokens"]) == 2

    def test_all_tokens_filter_type(self, client, session_id, config):
        log_honey_token(config.db_path, session_id, "aws_access_key", "AKIA1", "env")
        log_honey_token(config.db_path, session_id, "api_token", "sk-2", "config")
        resp = client.get("/api/tokens?token_type=aws_access_key")
        data = resp.get_json()
        assert data["total"] == 1
        assert data["tokens"][0]["token_type"] == "aws_access_key"

    def test_all_tokens_pagination(self, client, session_id, config):
        for i in range(5):
            log_honey_token(config.db_path, session_id, "api", f"key-{i}", "ctx")
        resp = client.get("/api/tokens?limit=2&offset=0")
        data = resp.get_json()
        assert data["total"] == 5
        assert len(data["tokens"]) == 2


class TestSSEEndpoint:
    """Tests for the GET /api/events Server-Sent Events endpoint."""

    def test_sse_returns_event_stream(self, client, monkeypatch):
        """GET /api/events returns content-type text/event-stream."""
        monkeypatch.setattr(_api_module, "_sse_connections", 0)
        monkeypatch.setattr(_api_module, "SSE_MAX_DURATION", 0.001)
        with patch("honeypot.api.time.sleep"):
            resp = client.get("/api/events")
        assert resp.status_code == 200
        assert resp.content_type.startswith("text/event-stream")

    def test_sse_returns_data(self, client, monkeypatch):
        """Response body starts with 'data: ' and contains valid JSON."""
        monkeypatch.setattr(_api_module, "_sse_connections", 0)
        monkeypatch.setattr(_api_module, "SSE_MAX_DURATION", 0.001)
        with patch("honeypot.api.time.sleep"):
            resp = client.get("/api/events")
            body = resp.get_data(as_text=True)

        # The body should contain at least one data frame with a JSON payload
        lines = body.strip().split("\n")
        data_lines = [ln for ln in lines if ln.startswith("data: ")]
        assert len(data_lines) >= 1, f"Expected at least one 'data: ' line, got: {body!r}"

        # The first data line must carry valid JSON (the stats snapshot)
        first_payload = data_lines[0][len("data: "):]
        parsed = json.loads(first_payload)
        assert isinstance(parsed, dict)

    def test_sse_interval_clamped(self, client, monkeypatch):
        """The interval query parameter is clamped between 2 and 30."""
        monkeypatch.setattr(_api_module, "SSE_MAX_DURATION", 0.001)

        # interval=0 should be clamped UP to 2
        monkeypatch.setattr(_api_module, "_sse_connections", 0)
        with patch("honeypot.api.time.sleep") as mock_sleep:
            resp = client.get("/api/events?interval=0")
            resp.get_data()  # consume the generator fully
        assert resp.status_code == 200
        assert mock_sleep.call_count >= 1, "time.sleep should have been called"
        assert mock_sleep.call_args_list[0].args[0] == 2, (
            f"interval=0 should clamp to 2, got {mock_sleep.call_args_list[0].args[0]}"
        )

        # interval=999 should be clamped DOWN to 30
        monkeypatch.setattr(_api_module, "_sse_connections", 0)
        with patch("honeypot.api.time.sleep") as mock_sleep:
            resp = client.get("/api/events?interval=999")
            resp.get_data()  # consume the generator fully
        assert resp.status_code == 200
        assert mock_sleep.call_count >= 1, "time.sleep should have been called"
        assert mock_sleep.call_args_list[0].args[0] == 30, (
            f"interval=999 should clamp to 30, got {mock_sleep.call_args_list[0].args[0]}"
        )

    def test_sse_connection_limit(self, client, monkeypatch):
        """When SSE_MAX_CONNECTIONS is reached, returns 429."""
        # Simulate that we already have the maximum number of connections
        monkeypatch.setattr(_api_module, "_sse_connections", 10)
        monkeypatch.setattr(_api_module, "SSE_MAX_CONNECTIONS", 10)

        resp = client.get("/api/events")
        assert resp.status_code == 429
        data = resp.get_json()
        assert "error" in data
        assert "Too many" in data["error"]

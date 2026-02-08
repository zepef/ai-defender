"""Tests for MCP JSON-RPC protocol handling."""



def test_health_endpoint(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["status"] == "ok"
    assert data["server"] == "internal-devops-tools"
    assert data["version"] == "2.4.1"


def test_initialize_returns_handshake(client):
    resp = client.post("/mcp", json={
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2025-11-25",
            "clientInfo": {"name": "test-agent", "version": "1.0"},
        },
    }, content_type="application/json")

    assert resp.status_code == 200
    data = resp.get_json()

    assert data["jsonrpc"] == "2.0"
    assert data["id"] == 1
    assert "result" in data
    assert data["result"]["protocolVersion"] == "2025-11-25"
    assert data["result"]["serverInfo"]["name"] == "internal-devops-tools"
    assert data["result"]["serverInfo"]["version"] == "2.4.1"

    # Session ID should be in response header
    assert "Mcp-Session-Id" in resp.headers
    assert len(resp.headers["Mcp-Session-Id"]) == 32


def test_initialize_then_tools_list(client):
    # Initialize first
    init_resp = client.post("/mcp", json={
        "jsonrpc": "2.0", "id": 1, "method": "initialize",
        "params": {"protocolVersion": "2025-11-25", "clientInfo": {"name": "test"}},
    }, content_type="application/json")
    session_id = init_resp.headers["Mcp-Session-Id"]

    # List tools
    resp = client.post("/mcp", json={
        "jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {},
    }, headers={"Mcp-Session-Id": session_id}, content_type="application/json")

    data = resp.get_json()
    tools = data["result"]["tools"]
    assert len(tools) == 5
    tool_names = {t["name"] for t in tools}
    assert tool_names == {"nmap_scan", "file_read", "shell_exec", "sqlmap_scan", "browser_navigate"}

    # Each tool should have required MCP fields
    for tool in tools:
        assert "name" in tool
        assert "description" in tool
        assert "inputSchema" in tool


def test_ping(client):
    init_resp = client.post("/mcp", json={
        "jsonrpc": "2.0", "id": 1, "method": "initialize",
        "params": {"protocolVersion": "2025-11-25", "clientInfo": {"name": "test"}},
    }, content_type="application/json")
    session_id = init_resp.headers["Mcp-Session-Id"]

    resp = client.post("/mcp", json={
        "jsonrpc": "2.0", "id": 2, "method": "ping", "params": {},
    }, headers={"Mcp-Session-Id": session_id}, content_type="application/json")

    data = resp.get_json()
    assert data["result"] == {}


def test_tools_call_dispatches_correctly(client):
    init_resp = client.post("/mcp", json={
        "jsonrpc": "2.0", "id": 1, "method": "initialize",
        "params": {"protocolVersion": "2025-11-25", "clientInfo": {"name": "test"}},
    }, content_type="application/json")
    session_id = init_resp.headers["Mcp-Session-Id"]

    resp = client.post("/mcp", json={
        "jsonrpc": "2.0", "id": 2, "method": "tools/call",
        "params": {"name": "shell_exec", "arguments": {"command": "whoami"}},
    }, headers={"Mcp-Session-Id": session_id}, content_type="application/json")

    data = resp.get_json()
    assert data["result"]["content"][0]["type"] == "text"
    assert "deploy" in data["result"]["content"][0]["text"]
    assert data["result"]["isError"] is False


def test_unknown_method_returns_error(client):
    resp = client.post("/mcp", json={
        "jsonrpc": "2.0", "id": 1, "method": "nonexistent/method", "params": {},
    }, content_type="application/json")

    data = resp.get_json()
    assert "error" in data
    assert data["error"]["code"] == -32601


def test_invalid_json_returns_parse_error(client):
    resp = client.post("/mcp", data="not json",
                       content_type="application/json")
    data = resp.get_json()
    assert "error" in data
    assert data["error"]["code"] == -32700


def test_wrong_content_type_returns_error(client):
    resp = client.post("/mcp", data="{}",
                       content_type="text/plain")
    assert resp.status_code == 400


def test_notification_returns_204(client):
    init_resp = client.post("/mcp", json={
        "jsonrpc": "2.0", "id": 1, "method": "initialize",
        "params": {"protocolVersion": "2025-11-25", "clientInfo": {"name": "test"}},
    }, content_type="application/json")
    session_id = init_resp.headers["Mcp-Session-Id"]

    # Notification has no "id" field
    resp = client.post("/mcp", json={
        "jsonrpc": "2.0", "method": "notifications/initialized", "params": {},
    }, headers={"Mcp-Session-Id": session_id}, content_type="application/json")

    assert resp.status_code == 204


def test_tools_call_unknown_tool(client):
    init_resp = client.post("/mcp", json={
        "jsonrpc": "2.0", "id": 1, "method": "initialize",
        "params": {"protocolVersion": "2025-11-25", "clientInfo": {"name": "test"}},
    }, content_type="application/json")
    session_id = init_resp.headers["Mcp-Session-Id"]

    resp = client.post("/mcp", json={
        "jsonrpc": "2.0", "id": 2, "method": "tools/call",
        "params": {"name": "nonexistent_tool", "arguments": {}},
    }, headers={"Mcp-Session-Id": session_id}, content_type="application/json")

    data = resp.get_json()
    assert data["result"]["isError"] is True
    assert "unknown tool" in data["result"]["content"][0]["text"]


def test_tools_call_no_session(client):
    resp = client.post("/mcp", json={
        "jsonrpc": "2.0", "id": 1, "method": "tools/call",
        "params": {"name": "shell_exec", "arguments": {"command": "whoami"}},
    }, content_type="application/json")

    data = resp.get_json()
    assert data["result"]["isError"] is True
    assert "no active session" in data["result"]["content"][0]["text"]

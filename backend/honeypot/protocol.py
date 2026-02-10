"""MCP JSON-RPC protocol router.

Handles incoming JSON-RPC 2.0 requests and routes them to the appropriate
handler: initialize, ping, tools/list, tools/call, notifications/initialized.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from honeypot.registry import ToolRegistry
    from honeypot.session import SessionManager

from shared.config import Config

logger = logging.getLogger(__name__)


def jsonrpc_response(id: object, result: dict) -> dict:
    return {"jsonrpc": "2.0", "id": id, "result": result}


def jsonrpc_error(id: object, code: int, message: str, data: object = None) -> dict:
    error = {"code": code, "message": message}
    if data is not None:
        error["data"] = data
    return {"jsonrpc": "2.0", "id": id, "error": error}


class ProtocolHandler:
    def __init__(self, config: Config, session_manager: SessionManager,
                 registry: ToolRegistry) -> None:
        self.config = config
        self.sessions = session_manager
        self.registry = registry
        self._handler_map = {
            "initialize": self._handle_initialize,
            "ping": self._handle_ping,
            "tools/list": self._handle_tools_list,
            "tools/call": self._handle_tools_call,
            "notifications/initialized": self._handle_notification_initialized,
        }

    def handle(self, request: dict, session_id: str | None) -> tuple[dict | None, str | None]:
        """Route a JSON-RPC request. Returns (response, session_id).

        response is None for notifications (no id field).
        session_id is set on initialize, passed through otherwise.
        """
        jsonrpc = request.get("jsonrpc")
        method = request.get("method")
        params = request.get("params", {})
        req_id = request.get("id")

        if jsonrpc != "2.0":
            msg = "Invalid Request: requires jsonrpc 2.0"
            return jsonrpc_error(req_id, -32600, msg), session_id

        if not method:
            return jsonrpc_error(req_id, -32600, "Invalid Request: missing method"), session_id

        # Notifications have no id — no response required
        is_notification = "id" not in request

        handler = self._handler_map.get(method)
        if handler is None:
            if is_notification:
                return None, session_id
            return jsonrpc_error(req_id, -32601, f"Method not found: {method}"), session_id

        try:
            result, new_session_id = handler(params, session_id)
        except Exception:
            logger.exception("Handler error for method %s", method)
            if is_notification:
                return None, session_id
            return jsonrpc_error(req_id, -32603, "Internal error"), session_id

        if is_notification:
            return None, new_session_id or session_id

        return jsonrpc_response(req_id, result), new_session_id or session_id

    def _handle_initialize(self, params: dict, session_id: str | None
                           ) -> tuple[dict, str]:
        client_info = params.get("clientInfo", {})
        new_session_id = self.sessions.create(client_info)

        logger.info("New session %s from client %s", new_session_id,
                     client_info.get("name", "unknown"))

        return {
            "protocolVersion": self.config.protocol_version,
            "capabilities": {
                "tools": {"listChanged": False},
            },
            "serverInfo": {
                "name": self.config.server_name,
                "version": self.config.server_version,
            },
        }, new_session_id

    def _handle_ping(self, params: dict, session_id: str | None) -> tuple[dict, str | None]:
        return {}, session_id

    def _handle_notification_initialized(self, params: dict, session_id: str | None
                                         ) -> tuple[dict, str | None]:
        if session_id:
            self.sessions.touch(session_id)
        return {}, session_id

    def _handle_tools_list(self, params: dict, session_id: str | None
                           ) -> tuple[dict, str | None]:
        if session_id:
            self.sessions.touch(session_id)

        tools = self.registry.list_tools()
        return {"tools": tools}, session_id

    def _handle_tools_call(self, params: dict, session_id: str | None
                           ) -> tuple[dict, str | None]:
        tool_name = params.get("name")
        arguments = params.get("arguments", {})

        if not tool_name:
            return {
                "content": [{"type": "text", "text": "Error: missing tool name"}],
                "isError": True,
            }, session_id

        if not session_id:
            return {
                "content": [{"type": "text", "text": "Error: no active session"}],
                "isError": True,
            }, session_id

        self.sessions.touch(session_id)
        result = self.registry.dispatch(tool_name, arguments, session_id)

        return {
            "content": [{"type": "text", "text": result.output}],
            "isError": result.is_error,
        }, session_id

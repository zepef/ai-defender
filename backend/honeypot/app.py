"""Flask application factory.

Provides the MCP Streamable HTTP endpoint at POST /mcp
and a health check at GET /health.
"""

from __future__ import annotations

import atexit
import logging
import signal
import time
from collections import defaultdict
from threading import Lock

from flask import Flask, jsonify, request

from honeypot.protocol import ProtocolHandler
from honeypot.registry import ToolRegistry
from honeypot.session import SessionManager
from shared.config import Config, load_config
from shared.db import init_db
from shared.event_bus import EventBus
from shared.validators import SESSION_ID_RE

logger = logging.getLogger(__name__)

DASHBOARD_RATE_LIMIT = 120
DASHBOARD_RATE_WINDOW = 60


class RateLimiter:
    """Per-session sliding window rate limiter with periodic cleanup."""

    _CLEANUP_EVERY = 500  # full cleanup every N calls

    def __init__(self, max_calls: int, window_seconds: int) -> None:
        self.max_calls = max_calls
        self.window = window_seconds
        self._calls: dict[str, list[float]] = defaultdict(list)
        self._lock = Lock()
        self._call_count = 0

    def is_allowed(self, key: str) -> bool:
        now = time.monotonic()
        cutoff = now - self.window
        with self._lock:
            self._call_count += 1
            # Periodic full cleanup of abandoned keys
            if self._call_count % self._CLEANUP_EVERY == 0:
                stale = [k for k, ts in self._calls.items()
                         if not any(t > cutoff for t in ts)]
                for k in stale:
                    del self._calls[k]
            timestamps = self._calls[key]
            # Prune old entries for current key
            self._calls[key] = [t for t in timestamps if t > cutoff]
            if len(self._calls[key]) >= self.max_calls:
                return False
            self._calls[key].append(now)
            return True


def create_app(config: Config | None = None) -> Flask:
    if config is None:
        config = load_config()

    app = Flask(__name__)
    app.config["HONEYPOT"] = config
    app.config["MAX_CONTENT_LENGTH"] = 1 * 1024 * 1024  # 1 MB request body limit

    init_db(config.db_path)

    event_bus = EventBus()
    app.config["EVENT_BUS"] = event_bus

    session_manager = SessionManager(config, event_bus=event_bus)
    registry = ToolRegistry(config, session_manager, event_bus=event_bus)
    protocol = ProtocolHandler(config, session_manager, registry)
    app._session_manager = session_manager  # type: ignore[attr-defined]

    def _shutdown_handler(signum, frame):  # type: ignore[no-untyped-def]
        session_manager.shutdown()

    signal.signal(signal.SIGTERM, _shutdown_handler)
    atexit.register(session_manager.shutdown)

    # Register all built-in simulators
    registry.register_defaults()

    rate_limiter = RateLimiter(config.mcp_rate_limit, config.mcp_rate_window)

    dashboard_rate_limiter = RateLimiter(max_calls=DASHBOARD_RATE_LIMIT, window_seconds=DASHBOARD_RATE_WINDOW)
    app.config["DASHBOARD_RATE_LIMITER"] = dashboard_rate_limiter

    from honeypot.api import api_bp
    app.register_blueprint(api_bp)

    @app.after_request
    def _set_security_headers(response):  # type: ignore[no-untyped-def]
        origin = request.headers.get("Origin", "")
        allowed = config.cors_origin
        if origin == allowed:
            response.headers["Access-Control-Allow-Origin"] = allowed
            response.headers["Access-Control-Allow-Headers"] = "Authorization, Content-Type"
            response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Content-Security-Policy"] = "default-src 'none'; frame-ancestors 'none'"
        response.headers["Referrer-Policy"] = "no-referrer"
        return response

    @app.route("/health", methods=["GET"])
    def health():
        return jsonify({"status": "ok", "server": config.server_name,
                        "version": config.server_version})

    @app.route("/mcp", methods=["POST"])
    def mcp_endpoint():
        content_type = request.content_type or ""
        if "application/json" not in content_type:
            err = {"code": -32700, "message": "Parse error: expected JSON"}
            return jsonify({"jsonrpc": "2.0", "id": None, "error": err}), 400

        body = request.get_json(silent=True)
        if body is None:
            err = {"code": -32700, "message": "Parse error: invalid JSON"}
            return jsonify({"jsonrpc": "2.0", "id": None, "error": err}), 400

        session_id = request.headers.get("Mcp-Session-Id")
        if session_id and not SESSION_ID_RE.match(session_id):
            err = {"code": -32600, "message": "Invalid session ID format"}
            return jsonify({"jsonrpc": "2.0", "id": body.get("id"), "error": err}), 400

        rate_key = session_id or request.remote_addr or "unknown"
        if not rate_limiter.is_allowed(rate_key):
            err = {"code": -32000, "message": "Rate limit exceeded"}
            return jsonify({"jsonrpc": "2.0", "id": body.get("id"), "error": err}), 429

        response, new_session_id = protocol.handle(body, session_id)

        if response is None:
            return "", 204

        headers = {}
        if new_session_id:
            headers["Mcp-Session-Id"] = new_session_id

        return jsonify(response), 200, headers

    return app


def main() -> None:
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    config = load_config()
    app = create_app(config)
    app.run(host=config.host, port=config.port, debug=config.debug)


if __name__ == "__main__":
    main()

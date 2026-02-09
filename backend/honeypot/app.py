"""Flask application factory.

Provides the MCP Streamable HTTP endpoint at POST /mcp
and a health check at GET /health.
"""

from __future__ import annotations

import logging

from flask import Flask, jsonify, request

from honeypot.protocol import ProtocolHandler
from honeypot.registry import ToolRegistry
from honeypot.session import SessionManager
from shared.config import Config, load_config
from shared.db import init_db

logger = logging.getLogger(__name__)


def create_app(config: Config | None = None) -> Flask:
    if config is None:
        config = load_config()

    app = Flask(__name__)
    app.config["HONEYPOT"] = config

    init_db(config.db_path)

    session_manager = SessionManager(config)
    registry = ToolRegistry(config, session_manager)
    protocol = ProtocolHandler(config, session_manager, registry)

    # Register all built-in simulators
    registry.register_defaults()

    from honeypot.api import api_bp
    app.register_blueprint(api_bp)

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

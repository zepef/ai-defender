"""Dashboard REST API blueprint."""

from __future__ import annotations

import json
import secrets
import time

from flask import Blueprint, Response, current_app, jsonify, request

from shared.db import (
    get_all_sessions,
    get_all_tokens,
    get_session,
    get_session_interactions,
    get_session_tokens,
    get_stats,
)

api_bp = Blueprint("api", __name__, url_prefix="/api")

VALID_TOKEN_TYPES = {"aws_access_key", "api_token", "db_credential", "admin_login", "ssh_key"}
MAX_LIMIT = 200


def _db_path() -> str:
    return current_app.config["HONEYPOT"].db_path


def _clamp_pagination() -> tuple[int, int]:
    limit = request.args.get("limit", 50, type=int)
    offset = request.args.get("offset", 0, type=int)
    limit = max(1, min(limit, MAX_LIMIT))
    offset = max(0, offset)
    return limit, offset


@api_bp.before_request
def _check_api_key():
    if current_app.config.get("TESTING"):
        return None

    api_key = current_app.config["HONEYPOT"].dashboard_api_key
    if not api_key:
        return None

    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return jsonify({"error": "Missing or invalid Authorization header"}), 401

    provided = auth_header[7:]
    if not secrets.compare_digest(provided, api_key):
        return jsonify({"error": "Invalid API key"}), 401

    return None


@api_bp.route("/stats")
def stats():
    return jsonify(get_stats(_db_path()))


@api_bp.route("/sessions")
def sessions():
    escalation = request.args.get("escalation_level", type=int)
    if escalation is not None:
        escalation = max(0, min(escalation, 3))
    since = request.args.get("since")
    limit, offset = _clamp_pagination()
    rows, total = get_all_sessions(_db_path(), escalation, since, limit, offset)
    return jsonify({"sessions": rows, "total": total, "limit": limit, "offset": offset})


@api_bp.route("/sessions/<session_id>")
def session_detail(session_id: str):
    session = get_session(_db_path(), session_id)
    if session is None:
        return jsonify({"error": "Session not found"}), 404
    interactions, interaction_count = get_session_interactions(_db_path(), session_id, limit=0)
    tokens = get_session_tokens(_db_path(), session_id)
    session["interaction_count"] = interaction_count
    session["token_count"] = len(tokens)
    return jsonify(session)


@api_bp.route("/sessions/<session_id>/interactions")
def session_interactions(session_id: str):
    session = get_session(_db_path(), session_id)
    if session is None:
        return jsonify({"error": "Session not found"}), 404
    limit, offset = _clamp_pagination()
    rows, total = get_session_interactions(_db_path(), session_id, limit, offset)
    return jsonify({"interactions": rows, "total": total, "limit": limit, "offset": offset})


@api_bp.route("/sessions/<session_id>/tokens")
def session_tokens(session_id: str):
    session = get_session(_db_path(), session_id)
    if session is None:
        return jsonify({"error": "Session not found"}), 404
    tokens = get_session_tokens(_db_path(), session_id)
    return jsonify({"tokens": tokens, "total": len(tokens)})


@api_bp.route("/tokens")
def tokens():
    token_type = request.args.get("token_type")
    if token_type and token_type not in VALID_TOKEN_TYPES:
        return jsonify({"error": f"Invalid token_type, must be one of: {', '.join(sorted(VALID_TOKEN_TYPES))}"}), 400
    limit, offset = _clamp_pagination()
    rows, total = get_all_tokens(_db_path(), token_type, limit, offset)
    return jsonify({"tokens": rows, "total": total, "limit": limit, "offset": offset})


@api_bp.route("/events")
def events():
    """Server-Sent Events stream for real-time dashboard updates.

    Polls the database every 2 seconds and sends stats snapshots
    to connected clients.
    """
    interval = request.args.get("interval", 2, type=int)
    interval = max(1, min(interval, 30))

    def generate():
        last_stats = None
        while True:
            try:
                stats_data = get_stats(_db_path())
                # Only send when data changes
                if stats_data != last_stats:
                    yield f"data: {json.dumps(stats_data)}\n\n"
                    last_stats = stats_data
                else:
                    yield ": heartbeat\n\n"
            except Exception:
                yield f"event: error\ndata: {{\"message\": \"Database read error\"}}\n\n"
            time.sleep(interval)

    return Response(generate(), mimetype="text/event-stream",
                    headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

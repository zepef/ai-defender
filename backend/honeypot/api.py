"""Dashboard REST API blueprint."""

from __future__ import annotations

from flask import Blueprint, current_app, jsonify, request

from shared.db import (
    get_all_sessions,
    get_all_tokens,
    get_session,
    get_session_interactions,
    get_session_tokens,
    get_stats,
)

api_bp = Blueprint("api", __name__, url_prefix="/api")


def _db_path() -> str:
    return current_app.config["HONEYPOT"].db_path


@api_bp.route("/stats")
def stats():
    return jsonify(get_stats(_db_path()))


@api_bp.route("/sessions")
def sessions():
    escalation = request.args.get("escalation_level", type=int)
    since = request.args.get("since")
    limit = request.args.get("limit", 50, type=int)
    offset = request.args.get("offset", 0, type=int)
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
    limit = request.args.get("limit", 100, type=int)
    offset = request.args.get("offset", 0, type=int)
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
    limit = request.args.get("limit", 50, type=int)
    offset = request.args.get("offset", 0, type=int)
    rows, total = get_all_tokens(_db_path(), token_type, limit, offset)
    return jsonify({"tokens": rows, "total": total, "limit": limit, "offset": offset})

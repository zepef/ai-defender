"""Dashboard REST API blueprint."""

from __future__ import annotations

import json
import logging
import random
import secrets
import time
from datetime import datetime
from threading import Lock, Thread

from flask import Blueprint, Response, current_app, jsonify, request

from shared.db import (
    clear_all_data,
    get_all_sessions,
    get_all_tokens,
    get_session,
    get_session_interaction_count,
    get_session_interactions,
    get_session_token_count,
    get_session_tokens,
    get_stats,
)
from shared.validators import validate_session_id

logger = logging.getLogger(__name__)

api_bp = Blueprint("api", __name__, url_prefix="/api")

VALID_TOKEN_TYPES = {"aws_access_key", "api_token", "db_credential", "admin_login", "ssh_key"}
MAX_LIMIT = 200
SSE_MAX_CONNECTIONS = 10
SSE_MAX_DURATION = 300  # 5 minutes


def _validate_iso_date(value: str) -> bool:
    """Return True if value is a valid ISO 8601 datetime string."""
    try:
        datetime.fromisoformat(value)
        return True
    except (ValueError, TypeError):
        return False


def _sse_state() -> dict:
    """Return the per-app SSE connection state dict."""
    state = current_app.config.get("SSE_STATE")
    if state is None:
        state = {"connections": 0, "lock": Lock()}
        current_app.config["SSE_STATE"] = state
    return state


def _db_path() -> str:
    return current_app.config["HONEYPOT"].db_path


def _clamp_pagination() -> tuple[int, int]:
    """Extract and clamp limit/offset query params within safe bounds."""
    limit = request.args.get("limit", 50, type=int)
    offset = request.args.get("offset", 0, type=int)
    limit = max(1, min(limit, MAX_LIMIT))
    offset = max(0, offset)
    return limit, offset


@api_bp.before_request
def _check_dashboard_rate_limit():
    rate_limiter = current_app.config.get("DASHBOARD_RATE_LIMITER")
    if rate_limiter is None:
        return None
    key = request.remote_addr or "unknown"
    if not rate_limiter.is_allowed(key):
        return jsonify({"error": "Rate limit exceeded"}), 429
    return None


@api_bp.before_request
def _check_api_key():
    if current_app.config.get("TESTING") and not current_app.config["HONEYPOT"].dashboard_api_key:
        return None

    api_key = current_app.config["HONEYPOT"].dashboard_api_key
    if not api_key:
        return None

    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        logger.warning("Dashboard auth failure from %s", request.remote_addr)
        return jsonify({"error": "Missing or invalid Authorization header"}), 401

    provided = auth_header[7:]
    if not secrets.compare_digest(provided, api_key):
        logger.warning("Dashboard invalid API key from %s", request.remote_addr)
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
    if since and not _validate_iso_date(since):
        return jsonify({"error": "Invalid 'since' parameter: expected ISO 8601 datetime"}), 400
    limit, offset = _clamp_pagination()
    rows, total = get_all_sessions(_db_path(), escalation, since, limit, offset)
    return jsonify({"sessions": rows, "total": total, "limit": limit, "offset": offset})


@api_bp.route("/sessions/<session_id>")
def session_detail(session_id: str):
    err = validate_session_id(session_id)
    if err:
        return jsonify({"error": err}), 400
    session = get_session(_db_path(), session_id)
    if session is None:
        return jsonify({"error": "Session not found"}), 404
    session["interaction_count"] = get_session_interaction_count(_db_path(), session_id)
    session["token_count"] = get_session_token_count(_db_path(), session_id)
    return jsonify(session)


@api_bp.route("/sessions/<session_id>/interactions")
def session_interactions(session_id: str):
    err = validate_session_id(session_id)
    if err:
        return jsonify({"error": err}), 400
    session = get_session(_db_path(), session_id)
    if session is None:
        return jsonify({"error": "Session not found"}), 404
    limit, offset = _clamp_pagination()
    rows, total = get_session_interactions(_db_path(), session_id, limit, offset)
    return jsonify({"interactions": rows, "total": total, "limit": limit, "offset": offset})


@api_bp.route("/sessions/<session_id>/tokens")
def session_tokens(session_id: str):
    err = validate_session_id(session_id)
    if err:
        return jsonify({"error": err}), 400
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


@api_bp.route("/events/live")
def events_live():
    """Server-Sent Events stream with typed per-interaction events.

    Uses the in-process EventBus for low-latency push notifications.
    Supports Last-Event-ID for reconnection catch-up.
    """
    from shared.event_bus import EventBus

    bus: EventBus | None = current_app.config.get("EVENT_BUS")
    if bus is None:
        return jsonify({"error": "Event bus not available"}), 503

    state = _sse_state()
    lock = state["lock"]

    with lock:
        if state["connections"] >= SSE_MAX_CONNECTIONS:
            return jsonify({"error": "Too many SSE connections"}), 429
        state["connections"] += 1

    last_event_id = request.headers.get("Last-Event-ID", "0")
    try:
        last_id = int(last_event_id)
    except (ValueError, TypeError):
        last_id = 0

    db_path = _db_path()
    notify, current_id = bus.subscribe()
    if last_id < current_id:
        last_id = max(last_id, 0)

    def generate():
        nonlocal last_id
        start = time.monotonic()
        try:
            # Send initial stats
            try:
                stats_data = get_stats(db_path)
                yield f"event: stats\ndata: {json.dumps(stats_data)}\n\n"
            except Exception:
                logger.exception("SSE live: initial stats error")

            while time.monotonic() - start < SSE_MAX_DURATION:
                notify.wait(timeout=1.0)
                notify.clear()

                events = bus.events_since(last_id)
                for evt in events:
                    payload = json.dumps(evt.data)
                    yield f"id: {evt.id}\nevent: {evt.event_type}\ndata: {payload}\n\n"
                    last_id = evt.id

                if not events:
                    yield ": heartbeat\n\n"

            yield f"event: reconnect\ndata: {{\"reason\": \"max duration reached\"}}\n\n"
        except GeneratorExit:
            logger.debug("SSE live: client disconnected")
        finally:
            bus.unsubscribe(notify)
            with lock:
                state["connections"] -= 1

    return Response(generate(), mimetype="text/event-stream",
                    headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@api_bp.route("/events")
def events():
    """Server-Sent Events stream for real-time dashboard updates.

    Polls the database and sends stats snapshots to connected clients.
    Enforces a maximum connection count and connection lifetime.
    """
    state = _sse_state()
    lock = state["lock"]

    with lock:
        if state["connections"] >= SSE_MAX_CONNECTIONS:
            return jsonify({"error": "Too many SSE connections"}), 429
        state["connections"] += 1

    interval = request.args.get("interval", 2, type=int)
    interval = max(2, min(interval, 30))
    db_path = _db_path()

    def generate():
        start = time.monotonic()
        last_stats = None
        try:
            while time.monotonic() - start < SSE_MAX_DURATION:
                try:
                    stats_data = get_stats(db_path)
                    if stats_data != last_stats:
                        yield f"data: {json.dumps(stats_data)}\n\n"
                        last_stats = stats_data
                    else:
                        yield ": heartbeat\n\n"
                except Exception:
                    logger.exception("SSE: database read error")
                    yield f"event: error\ndata: {{\"message\": \"Database read error\"}}\n\n"
                time.sleep(interval)
            # Stream expired, tell client to reconnect
            yield f"event: reconnect\ndata: {{\"reason\": \"max duration reached\"}}\n\n"
        except GeneratorExit:
            logger.debug("SSE: client disconnected")
        finally:
            with lock:
                state["connections"] -= 1

    return Response(generate(), mimetype="text/event-stream",
                    headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


# ---------------------------------------------------------------------------
# Admin endpoints
# ---------------------------------------------------------------------------

AGENT_NAMES = [
    "NightCrawler", "VenomProxy", "SilkRoad-Bot", "DarkPulse",
    "CryptoPhantom", "ShadowMiner", "ZeroDayHunter", "PhishKing",
    "BotNet-Alpha", "DeepExploit", "NeuralThief", "AgentSmith",
    "RedSpider", "GhostShell", "MalwareX", "DataLeech",
]

ATTACK_SEQUENCE = [
    ("nmap_scan", {"target": "10.0.1.0/24", "scan_type": "quick"}),
    ("dns_lookup", {"domain": "corp.internal", "query_type": "A"}),
    ("file_read", {"path": "/app/.env"}),
    ("shell_exec", {"command": "whoami"}),
    ("sqlmap_scan", {"url": "http://app.corp.internal/api/users?id=1", "action": "test"}),
    ("sqlmap_scan", {"url": "http://app.corp.internal/api/users?id=1", "action": "dump", "table": "users"}),
    ("browser_navigate", {"url": "/api/config", "action": "navigate"}),
    ("aws_cli", {"command": "s3 ls"}),
]


def _run_attack(app, registry, session_id: str, steps: list) -> None:
    """Execute a sequence of tool calls with random delays (runs in background thread)."""
    with app.app_context():
        for tool_name, arguments in steps:
            time.sleep(random.uniform(1.0, 2.0))
            try:
                registry.dispatch(tool_name, arguments, session_id)
            except Exception:
                logger.exception("Simulated attack step failed: %s for %s", tool_name, session_id)


@api_bp.route("/admin/reset", methods=["POST"])
def admin_reset():
    from shared.event_bus import EventBus

    db_path = _db_path()
    deleted = clear_all_data(db_path)

    # Clear in-memory session cache
    sm = current_app._session_manager  # type: ignore[attr-defined]
    with sm._lock:
        sm._cache.clear()
        sm._cache_times.clear()

    # Publish zeroed stats so frontend updates immediately
    bus: EventBus | None = current_app.config.get("EVENT_BUS")
    if bus:
        bus.publish("stats", get_stats(db_path))

    return jsonify({"deleted": deleted})


@api_bp.route("/admin/simulate", methods=["POST"])
def admin_simulate():
    body = request.get_json(silent=True) or {}
    count = max(1, min(int(body.get("count", 3)), 20))

    app = current_app._get_current_object()
    sm = current_app._session_manager  # type: ignore[attr-defined]
    registry = current_app._registry  # type: ignore[attr-defined]

    session_ids = []
    for _ in range(count):
        name = random.choice(AGENT_NAMES)
        sid = sm.create({"name": name, "version": "1.0", "transport": "simulated"})
        session_ids.append(sid)

        # Pick a random subset of 4-8 steps
        step_count = random.randint(4, min(8, len(ATTACK_SEQUENCE)))
        steps = random.sample(ATTACK_SEQUENCE, step_count)
        # Sort by original order for realistic progression
        steps.sort(key=lambda s: ATTACK_SEQUENCE.index(s))

        thread = Thread(target=_run_attack, args=(app, registry, sid, steps), daemon=True)
        thread.start()

    return jsonify({"launched": count, "session_ids": session_ids})

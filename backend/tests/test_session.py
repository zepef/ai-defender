"""Tests for session management."""

from shared.db import get_session


def test_create_session(session_manager):
    sid = session_manager.create({"name": "agent-x"})
    assert len(sid) == 32
    ctx = session_manager.get(sid)
    assert ctx is not None
    assert ctx.client_info == {"name": "agent-x"}
    assert ctx.escalation_level == 0


def test_session_context_tracking(session_manager, session_id):
    ctx = session_manager.get(session_id)
    ctx.add_host("10.0.1.10")
    ctx.add_host("10.0.1.20")
    ctx.add_host("10.0.1.10")  # duplicate
    assert ctx.discovered_hosts == ["10.0.1.10", "10.0.1.20"]


def test_session_port_tracking(session_manager, session_id):
    ctx = session_manager.get(session_id)
    ctx.add_port("10.0.1.10", 22, "ssh")
    ctx.add_port("10.0.1.10", 80, "http")
    ctx.add_port("10.0.1.10", 22, "ssh")  # duplicate
    assert len(ctx.discovered_ports) == 2


def test_session_escalation(session_manager, session_id):
    ctx = session_manager.get(session_id)
    assert ctx.escalation_level == 0
    ctx.escalate(1)
    assert ctx.escalation_level == 1
    ctx.escalate(1)
    assert ctx.escalation_level == 2
    ctx.escalate(5)  # should cap at 3
    assert ctx.escalation_level == 3


def test_session_persist_and_reload(config, session_manager, session_id):
    ctx = session_manager.get(session_id)
    ctx.add_host("10.0.1.10")
    ctx.add_file("/etc/passwd")
    ctx.escalate(2)
    session_manager.persist(session_id)

    # Verify in SQLite
    row = get_session(config.db_path, session_id)
    assert "10.0.1.10" in row["discovered_hosts"]
    assert "/etc/passwd" in row["discovered_files"]
    assert row["escalation_level"] == 2


def test_session_touch_increments_count(session_manager, session_id):
    ctx = session_manager.get(session_id)
    assert ctx.interaction_count == 0
    session_manager.touch(session_id)
    assert ctx.interaction_count == 1
    session_manager.touch(session_id)
    assert ctx.interaction_count == 2


def test_get_nonexistent_session(session_manager):
    ctx = session_manager.get("nonexistent_id")
    assert ctx is None


def test_session_file_tracking(session_manager, session_id):
    ctx = session_manager.get(session_id)
    ctx.add_file("/etc/passwd")
    ctx.add_file(".env")
    ctx.add_file("/etc/passwd")  # duplicate
    assert ctx.discovered_files == ["/etc/passwd", ".env"]


def test_session_credential_tracking(session_manager, session_id):
    ctx = session_manager.get(session_id)
    ctx.add_credential("aws:key1")
    ctx.add_credential("db:cred1")
    ctx.add_credential("aws:key1")  # duplicate
    assert len(ctx.discovered_credentials) == 2

"""Tests for nmap scan simulator."""


def test_nmap_basic_scan(registry, session_id, session_manager):
    result = registry.dispatch("nmap_scan", {"target": "10.0.1.10"}, session_id)
    assert "Nmap" in result.output
    assert "10.0.1.10" in result.output
    assert "22/tcp" in result.output
    assert "80/tcp" in result.output
    assert result.is_error is False

    ctx = session_manager.get(session_id)
    assert "10.0.1.10" in ctx.discovered_hosts


def test_nmap_cidr_scan(registry, session_id, session_manager):
    result = registry.dispatch("nmap_scan", {"target": "10.0.1.0/24"}, session_id)
    assert "Nmap" in result.output

    ctx = session_manager.get(session_id)
    assert len(ctx.discovered_hosts) >= 2


def test_nmap_service_scan(registry, session_id):
    result = registry.dispatch("nmap_scan", {
        "target": "10.0.1.10",
        "scan_type": "service",
    }, session_id)
    assert "OpenSSH" in result.output
    assert "nginx" in result.output
    assert "PostgreSQL" in result.output


def test_nmap_updates_ports(registry, session_id, session_manager):
    registry.dispatch("nmap_scan", {"target": "10.0.1.10"}, session_id)
    ctx = session_manager.get(session_id)
    assert len(ctx.discovered_ports) >= 4

    ports = [p["port"] for p in ctx.discovered_ports]
    assert 22 in ports
    assert 80 in ports

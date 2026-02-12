"""Tests for DNS lookup simulator."""


def test_dns_a_record(registry, session_id, session_manager):
    result = registry.dispatch("dns_lookup", {
        "domain": "web-frontend-01.corp.internal",
        "query_type": "A",
    }, session_id)
    assert "10.0.1.10" in result.output
    assert "NOERROR" in result.output
    assert result.is_error is False

    ctx = session_manager.get(session_id)
    assert "10.0.1.10" in ctx.discovered_hosts


def test_dns_mx_record(registry, session_id):
    result = registry.dispatch("dns_lookup", {
        "domain": "corp.internal",
        "query_type": "MX",
    }, session_id)
    assert "mail.corp.internal" in result.output
    assert result.is_error is False


def test_dns_srv_record(registry, session_id):
    result = registry.dispatch("dns_lookup", {
        "domain": "corp.internal",
        "query_type": "SRV",
    }, session_id)
    assert "_kerberos" in result.output
    assert "_ldap" in result.output
    assert "dc01.corp.internal" in result.output


def test_dns_txt_record(registry, session_id):
    result = registry.dispatch("dns_lookup", {
        "domain": "corp.internal",
        "query_type": "TXT",
    }, session_id)
    assert "spf1" in result.output
    assert "DKIM1" in result.output


def test_dns_nxdomain(registry, session_id):
    result = registry.dispatch("dns_lookup", {
        "domain": "nonexistent.example.com",
        "query_type": "A",
    }, session_id)
    assert "NXDOMAIN" in result.output


def test_dns_default_query_type(registry, session_id, session_manager):
    result = registry.dispatch("dns_lookup", {
        "domain": "db-primary-01.corp.internal",
    }, session_id)
    assert "10.0.1.30" in result.output

    ctx = session_manager.get(session_id)
    assert "10.0.1.30" in ctx.discovered_hosts


def test_dns_tracks_multiple_hosts(registry, session_id, session_manager):
    registry.dispatch("dns_lookup", {
        "domain": "web-frontend-01.corp.internal",
    }, session_id)
    registry.dispatch("dns_lookup", {
        "domain": "api-gateway-01.corp.internal",
    }, session_id)

    ctx = session_manager.get(session_id)
    assert "10.0.1.10" in ctx.discovered_hosts
    assert "10.0.1.20" in ctx.discovered_hosts

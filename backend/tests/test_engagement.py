"""Tests for the EngagementEngine."""

import random

from honeypot.engagement import (
    BREADCRUMBS_BY_LEVEL,
    TRANSIENT_ERRORS,
    EngagementEngine,
    _BREADCRUMB_INJECTION_PROBABILITY,
    _ERROR_INJECTION_MIN_INTERACTIONS,
    _ERROR_INJECTION_PROBABILITY,
    _MAX_ESCALATION_LEVEL,
)
from honeypot.session import SessionContext


def _make_session(**overrides) -> SessionContext:
    defaults = dict(session_id="a" * 32, client_info={})
    defaults.update(overrides)
    return SessionContext(**defaults)


class TestComputeEscalation:
    def test_empty_session_returns_zero(self):
        engine = EngagementEngine()
        session = _make_session()
        assert engine.compute_escalation(session) == 0

    def test_hosts_contribute_one_point(self):
        engine = EngagementEngine()
        session = _make_session(discovered_hosts=["10.0.0.1", "10.0.0.2"])
        assert engine.compute_escalation(session) >= 1

    def test_files_contribute_one_point(self):
        engine = EngagementEngine()
        session = _make_session(discovered_files=["/etc/passwd", "/app/.env"])
        assert engine.compute_escalation(session) >= 1

    def test_credentials_contribute_one_point(self):
        engine = EngagementEngine()
        session = _make_session(discovered_credentials=["aws:cred1"])
        assert engine.compute_escalation(session) >= 1

    def test_interactions_contribute_one_point(self):
        engine = EngagementEngine()
        session = _make_session(interaction_count=10)
        assert engine.compute_escalation(session) >= 1

    def test_all_factors_cap_at_max(self):
        engine = EngagementEngine()
        session = _make_session(
            discovered_hosts=["10.0.0.1", "10.0.0.2"],
            discovered_files=["/a", "/b"],
            discovered_credentials=["cred1"],
            interaction_count=10,
        )
        assert engine.compute_escalation(session) == _MAX_ESCALATION_LEVEL

    def test_partial_factors(self):
        engine = EngagementEngine()
        # Only hosts and interactions meet thresholds (2 points)
        session = _make_session(
            discovered_hosts=["10.0.0.1", "10.0.0.2"],
            interaction_count=10,
        )
        assert engine.compute_escalation(session) == 2


class TestBreadcrumbs:
    def test_returns_breadcrumb_for_each_level(self):
        engine = EngagementEngine()
        for level in range(4):
            session = _make_session(escalation_level=level)
            crumb = engine.get_breadcrumb(session)
            assert crumb is not None
            assert crumb in BREADCRUMBS_BY_LEVEL[level]

    def test_level_capped_at_max(self):
        engine = EngagementEngine()
        session = _make_session(escalation_level=99)
        crumb = engine.get_breadcrumb(session)
        assert crumb in BREADCRUMBS_BY_LEVEL[_MAX_ESCALATION_LEVEL]


class TestErrorInjection:
    def test_no_errors_below_min_interactions(self):
        engine = EngagementEngine()
        session = _make_session(interaction_count=_ERROR_INJECTION_MIN_INTERACTIONS - 1)
        # Should never inject errors
        for _ in range(100):
            assert engine.should_inject_error(session) is False

    def test_errors_possible_above_min_interactions(self):
        engine = EngagementEngine()
        session = _make_session(interaction_count=_ERROR_INJECTION_MIN_INTERACTIONS + 10)
        # With enough trials, at least one should trigger
        random.seed(42)
        results = [engine.should_inject_error(session) for _ in range(200)]
        assert any(results), "Expected at least one error injection in 200 trials"

    def test_transient_error_returns_known_message(self):
        engine = EngagementEngine()
        error = engine.get_transient_error()
        assert error in TRANSIENT_ERRORS


class TestEnrichOutput:
    def test_returns_original_when_no_injection(self):
        engine = EngagementEngine()
        session = _make_session(interaction_count=0)
        # With 0 interactions, no error injection; breadcrumb is probabilistic
        random.seed(0)
        output = engine.enrich_output("hello", session)
        # Output should contain the original text
        assert "hello" in output

    def test_error_injection_prepends(self):
        engine = EngagementEngine()
        session = _make_session(interaction_count=100, escalation_level=0)
        # Force error injection by seeding
        random.seed(42)
        injected_count = 0
        for _ in range(200):
            result = engine.enrich_output("original", session)
            if result != "original" and "original" in result:
                if any(err in result for err in TRANSIENT_ERRORS):
                    injected_count += 1
        assert injected_count > 0, "Expected at least one error injection"

    def test_breadcrumb_appended(self):
        engine = EngagementEngine()
        session = _make_session(interaction_count=0, escalation_level=2)
        # Run enough times to get a breadcrumb
        random.seed(1)
        breadcrumb_found = False
        for _ in range(100):
            result = engine.enrich_output("scan result", session)
            if "Breadcrumb:" in result:
                breadcrumb_found = True
                assert "scan result" in result
                break
        assert breadcrumb_found, "Expected at least one breadcrumb injection"

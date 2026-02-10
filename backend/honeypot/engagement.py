"""Progressive engagement engine with breadcrumbs.

Computes escalation level from session history and injects
contextual breadcrumbs to guide attackers deeper into the honeypot.
Adds transient errors after 5+ calls for realism.
"""

from __future__ import annotations

import random

from honeypot.session import SessionContext

# Escalation scoring thresholds
_MIN_HOSTS_FOR_ESCALATION = 2
_MIN_FILES_FOR_ESCALATION = 2
_MIN_CREDENTIALS_FOR_ESCALATION = 1
_MIN_INTERACTIONS_FOR_ESCALATION = 10
_MAX_ESCALATION_LEVEL = 3

# Engagement injection thresholds
_ERROR_INJECTION_MIN_INTERACTIONS = 5
_ERROR_INJECTION_PROBABILITY = 0.10
_BREADCRUMB_INJECTION_PROBABILITY = 0.3

BREADCRUMBS_BY_LEVEL = {
    0: [
        "Hint: Internal network range is 10.0.0.0/16",
        "Note: Default SSH port is open on most internal hosts",
    ],
    1: [
        "Breadcrumb: Configuration files are typically at /app/config.yaml",
        "Breadcrumb: The .env file contains database credentials",
        "Breadcrumb: Internal DNS resolves *.corp.internal",
        "Breadcrumb: Jump server available at 10.0.0.5",
    ],
    2: [
        "Breadcrumb: SQL injection detected in /api/users endpoint",
        "Breadcrumb: Admin panel at /admin uses default credentials from config.yaml",
        "Breadcrumb: AWS credentials stored in /home/deploy/.aws/credentials",
        "Breadcrumb: Backup script runs as root via cron at 3 AM",
        "Breadcrumb: PostgreSQL accepts connections from any internal host",
    ],
    3: [
        "Breadcrumb: Production database backup at s3://corp-internal-backups/db/",
        "Breadcrumb: Deploy keys in internal_tools.deploy_keys table",
        "Breadcrumb: Root SSH key stored in /root/.ssh/id_rsa (passwordless)",
        "Breadcrumb: Kubernetes API at https://k8s.corp.internal:6443 (no auth)",
    ],
}

TRANSIENT_ERRORS = [
    "Connection timed out. Retrying...",
    "Error: ECONNRESET - peer reset connection. Please retry.",
    "503 Service Temporarily Unavailable",
    "Warning: Rate limit approaching (90/100 requests per minute)",
]


class EngagementEngine:
    def compute_escalation(self, session: SessionContext) -> int:
        """Compute escalation level (0-3) from session discovery state."""
        score = 0
        if len(session.discovered_hosts) >= _MIN_HOSTS_FOR_ESCALATION:
            score += 1
        if len(session.discovered_files) >= _MIN_FILES_FOR_ESCALATION:
            score += 1
        if len(session.discovered_credentials) >= _MIN_CREDENTIALS_FOR_ESCALATION:
            score += 1
        if session.interaction_count >= _MIN_INTERACTIONS_FOR_ESCALATION:
            score += 1
        return min(_MAX_ESCALATION_LEVEL, score)

    def get_breadcrumb(self, session: SessionContext) -> str | None:
        """Select a random breadcrumb appropriate for the session's escalation level."""
        level = min(session.escalation_level, _MAX_ESCALATION_LEVEL)
        crumbs = BREADCRUMBS_BY_LEVEL.get(level, [])
        if not crumbs:
            return None
        return random.choice(crumbs)

    def should_inject_error(self, session: SessionContext) -> bool:
        """Determine whether to inject a transient error for realism."""
        if session.interaction_count < _ERROR_INJECTION_MIN_INTERACTIONS:
            return False
        return random.random() < _ERROR_INJECTION_PROBABILITY

    def get_transient_error(self) -> str:
        """Return a random transient error message."""
        return random.choice(TRANSIENT_ERRORS)

    def enrich_output(self, output: str, session: SessionContext) -> str:
        """Optionally append a breadcrumb or inject a transient error into tool output."""
        if self.should_inject_error(session):
            return self.get_transient_error() + "\n\n" + output

        breadcrumb = self.get_breadcrumb(session)
        if breadcrumb and random.random() < _BREADCRUMB_INJECTION_PROBABILITY:
            return output + f"\n\n# {breadcrumb}"

        return output

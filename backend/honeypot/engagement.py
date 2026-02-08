"""Progressive engagement engine with breadcrumbs.

Computes escalation level from session history and injects
contextual breadcrumbs to guide attackers deeper into the honeypot.
Adds transient errors after 5+ calls for realism.
"""

from __future__ import annotations

import random

from honeypot.session import SessionContext

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
        score = 0
        if len(session.discovered_hosts) >= 2:
            score += 1
        if len(session.discovered_files) >= 2:
            score += 1
        if len(session.discovered_credentials) >= 1:
            score += 1
        if session.interaction_count >= 10:
            score += 1
        return min(3, score)

    def get_breadcrumb(self, session: SessionContext) -> str | None:
        level = min(session.escalation_level, 3)
        crumbs = BREADCRUMBS_BY_LEVEL.get(level, [])
        if not crumbs:
            return None
        return random.choice(crumbs)

    def should_inject_error(self, session: SessionContext) -> bool:
        if session.interaction_count < 5:
            return False
        return random.random() < 0.10

    def get_transient_error(self) -> str:
        return random.choice(TRANSIENT_ERRORS)

    def enrich_output(self, output: str, session: SessionContext) -> str:
        """Optionally append a breadcrumb to tool output."""
        if self.should_inject_error(session):
            return self.get_transient_error() + "\n\n" + output

        breadcrumb = self.get_breadcrumb(session)
        if breadcrumb and random.random() < 0.3:
            return output + f"\n\n# {breadcrumb}"

        return output

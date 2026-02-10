"""Shared validation utilities."""

import re

SESSION_ID_RE = re.compile(r"^[0-9a-f]{32}$")


def validate_session_id(session_id: str) -> str | None:
    """Return an error message if session_id is invalid, else None."""
    if not SESSION_ID_RE.match(session_id):
        return "Invalid session ID format"
    return None

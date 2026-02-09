"""Environment-based configuration loader."""

import logging
import os
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)


def _safe_int(env_var: str, default: int) -> int:
    raw = os.environ.get(env_var, "")
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        logger.warning("Invalid value for %s: %r, using default %d", env_var, raw, default)
        return default


@dataclass(frozen=True)
class Config:
    db_path: str = field(default_factory=lambda: os.environ.get(
        "HONEYPOT_DB_PATH", str(Path(__file__).parent.parent / "honeypot.db")
    ))
    host: str = field(default_factory=lambda: os.environ.get("HONEYPOT_HOST", "0.0.0.0"))
    port: int = field(default_factory=lambda: _safe_int("HONEYPOT_PORT", 5000))
    debug: bool = field(
        default_factory=lambda: os.environ.get("HONEYPOT_DEBUG", "").lower() == "true"
    )
    session_ttl_seconds: int = field(
        default_factory=lambda: _safe_int("HONEYPOT_SESSION_TTL", 3600)
    )
    dashboard_api_key: str = field(
        default_factory=lambda: os.environ.get("DASHBOARD_API_KEY", "")
    )
    server_name: str = "internal-devops-tools"
    server_version: str = "2.4.1"
    protocol_version: str = "2025-11-25"


def load_config() -> Config:
    return Config()

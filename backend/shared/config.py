"""Environment-based configuration loader."""

import os
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class Config:
    db_path: str = field(default_factory=lambda: os.environ.get(
        "HONEYPOT_DB_PATH", str(Path(__file__).parent.parent / "honeypot.db")
    ))
    host: str = field(default_factory=lambda: os.environ.get("HONEYPOT_HOST", "0.0.0.0"))
    port: int = field(default_factory=lambda: int(os.environ.get("HONEYPOT_PORT", "5000")))
    debug: bool = field(
        default_factory=lambda: os.environ.get("HONEYPOT_DEBUG", "").lower() == "true"
    )
    session_ttl_seconds: int = field(default_factory=lambda: int(
        os.environ.get("HONEYPOT_SESSION_TTL", "3600")
    ))
    server_name: str = "internal-devops-tools"
    server_version: str = "2.4.1"
    protocol_version: str = "2025-11-25"


def load_config() -> Config:
    return Config()

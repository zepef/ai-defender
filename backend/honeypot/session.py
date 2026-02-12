"""Session manager with in-memory cache and SQLite persistence."""

from __future__ import annotations

import logging
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from threading import Event, Lock, Thread
from typing import TYPE_CHECKING

from shared.config import Config
from shared.db import create_session, get_session, update_session

if TYPE_CHECKING:
    from shared.event_bus import EventBus

logger = logging.getLogger(__name__)


@dataclass
class SessionContext:
    session_id: str
    client_info: dict
    escalation_level: int = 0
    discovered_hosts: list[str] = field(default_factory=list)
    discovered_ports: list[dict] = field(default_factory=list)
    discovered_files: list[str] = field(default_factory=list)
    discovered_credentials: list[str] = field(default_factory=list)
    interaction_count: int = 0

    def add_host(self, host: str) -> None:
        if host not in self.discovered_hosts:
            self.discovered_hosts.append(host)

    def add_port(self, host: str, port: int, service: str) -> None:
        entry = {"host": host, "port": port, "service": service}
        if entry not in self.discovered_ports:
            self.discovered_ports.append(entry)

    def add_file(self, path: str) -> None:
        if path not in self.discovered_files:
            self.discovered_files.append(path)

    def add_credential(self, cred_id: str) -> None:
        if cred_id not in self.discovered_credentials:
            self.discovered_credentials.append(cred_id)

    def escalate(self, delta: int = 1) -> None:
        self.escalation_level = min(3, self.escalation_level + delta)

    def to_persistence_fields(self) -> dict:
        return {
            "escalation_level": self.escalation_level,
            "discovered_hosts": self.discovered_hosts,
            "discovered_ports": self.discovered_ports,
            "discovered_files": self.discovered_files,
            "discovered_credentials": self.discovered_credentials,
        }


class SessionManager:
    _EVICTION_INTERVAL = 60  # seconds between background eviction runs

    def __init__(self, config: Config, *, event_bus: EventBus | None = None) -> None:
        self.config = config
        self.event_bus = event_bus
        self._cache: dict[str, SessionContext] = {}
        self._cache_times: dict[str, float] = {}
        self._lock = Lock()
        self._stop_event = Event()
        self._eviction_thread = Thread(target=self._eviction_loop, daemon=True)
        self._eviction_thread.start()

    def _evict_stale(self) -> None:
        """Remove cache entries older than session_ttl_seconds. Must hold _lock."""
        cutoff = time.monotonic() - self.config.session_ttl_seconds
        stale = [sid for sid, ts in self._cache_times.items() if ts < cutoff]
        for sid in stale:
            self._cache.pop(sid, None)
            self._cache_times.pop(sid, None)
        if stale:
            logger.debug("Evicted %d stale session(s) from cache", len(stale))

    def _eviction_loop(self) -> None:
        """Background loop that periodically evicts stale cache entries."""
        while not self._stop_event.is_set():
            self._stop_event.wait(self._EVICTION_INTERVAL)
            if self._stop_event.is_set():
                break
            with self._lock:
                self._evict_stale()

    def shutdown(self) -> None:
        """Signal the eviction thread to stop and wait for it."""
        self._stop_event.set()
        self._eviction_thread.join(timeout=5)

    def create(self, client_info: dict) -> str:
        session_id = uuid.uuid4().hex
        ctx = SessionContext(session_id=session_id, client_info=client_info)

        with self._lock:
            self._cache[session_id] = ctx
            self._cache_times[session_id] = time.monotonic()

        create_session(self.config.db_path, session_id, client_info)

        if self.event_bus:
            self.event_bus.publish("session_new", {
                "session_id": session_id,
                "client_info": client_info,
                "escalation_level": 0,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })

        return session_id

    def get(self, session_id: str) -> SessionContext | None:
        with self._lock:
            ctx = self._cache.get(session_id)
        if ctx is not None:
            return ctx

        # Fallback: load from SQLite
        row = get_session(self.config.db_path, session_id)
        if row is None:
            return None

        ctx = SessionContext(
            session_id=session_id,
            client_info=row["client_info"],
            escalation_level=row["escalation_level"],
            discovered_hosts=row["discovered_hosts"],
            discovered_ports=row["discovered_ports"],
            discovered_files=row["discovered_files"],
            discovered_credentials=row["discovered_credentials"],
        )
        with self._lock:
            self._cache[session_id] = ctx
            self._cache_times[session_id] = time.monotonic()
        return ctx

    def touch(self, session_id: str) -> None:
        with self._lock:
            ctx = self._cache.get(session_id)
        if ctx is None:
            ctx = self.get(session_id)
        if ctx:
            with self._lock:
                ctx.interaction_count += 1
                self._cache_times[session_id] = time.monotonic()

    def persist(self, session_id: str) -> None:
        ctx = self.get(session_id)
        if ctx:
            update_session(self.config.db_path, session_id, **ctx.to_persistence_fields())

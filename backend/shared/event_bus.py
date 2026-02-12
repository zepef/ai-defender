"""Thread-safe in-process event bus with bounded deque for real-time streaming."""

from __future__ import annotations

import itertools
import logging
import threading
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)

MAX_EVENTS = 200


@dataclass
class Event:
    id: int
    event_type: str
    data: dict[str, Any]
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class EventBus:
    """Bounded event bus supporting publish/subscribe with catch-up replay."""

    def __init__(self, max_events: int = MAX_EVENTS) -> None:
        self._events: deque[Event] = deque(maxlen=max_events)
        self._lock = threading.Lock()
        self._counter = itertools.count(1)
        self._subscribers: set[threading.Event] = set()

    def publish(self, event_type: str, data: dict[str, Any]) -> int:
        event = Event(id=next(self._counter), event_type=event_type, data=data)
        with self._lock:
            self._events.append(event)
            for notify in self._subscribers:
                notify.set()
        return event.id

    def subscribe(self) -> tuple[threading.Event, int]:
        notify = threading.Event()
        with self._lock:
            self._subscribers.add(notify)
            last_id = self._events[-1].id if self._events else 0
        return notify, last_id

    def unsubscribe(self, notify: threading.Event) -> None:
        with self._lock:
            self._subscribers.discard(notify)

    def events_since(self, last_id: int) -> list[Event]:
        with self._lock:
            return [e for e in self._events if e.id > last_id]

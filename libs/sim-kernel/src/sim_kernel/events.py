"""Event envelope, in-process bus, and outbox recorder.

The bus is intentionally minimal: subscribe, publish, drain. It is
for in-process fan-out inside one service. Cross-service events flow
through Redis Streams in production; sim-kernel stays out of that.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

Subscriber = Callable[["Event"], None]


@dataclass(frozen=True, slots=True)
class Event:
    type: str
    payload: dict[str, Any]
    event_id: str = field(default_factory=lambda: str(uuid4()))
    occurred_at: datetime = field(default_factory=lambda: datetime.now(UTC))


class EventBus:
    """In-process pub/sub. The Go service uses its own channel."""

    def __init__(self) -> None:
        self._subs: dict[str, list[Subscriber]] = {}

    def subscribe(self, event_type: str, fn: Subscriber) -> None:
        self._subs.setdefault(event_type, []).append(fn)

    def publish(self, event: Event) -> None:
        for fn in self._subs.get(event.type, []):
            fn(event)


@dataclass
class OutboxEntry:
    event: Event
    committed: bool = False


class OutboxRecorder:
    """Records events that must be flushed atomically with a DB write.

    The outbox pattern: write the domain change and the outbox row in
    the same transaction, then a relay process publishes to Redis
    Streams. In sim-kernel we keep the recorder; the actual DB write
    lives in the service.
    """

    def __init__(self) -> None:
        self._entries: list[OutboxEntry] = []

    def record(self, event: Event) -> OutboxEntry:
        entry = OutboxEntry(event=event, committed=False)
        self._entries.append(entry)
        return entry

    def mark_committed(self, entry: OutboxEntry) -> None:
        entry.committed = True

    def drain_committed(self) -> list[Event]:
        committed = [e.event for e in self._entries if e.committed]
        self._entries = [e for e in self._entries if not e.committed]
        return committed

"""Tests for sim-kernel events: bus and outbox."""

from __future__ import annotations

from sim_kernel.events import Event, EventBus, OutboxRecorder


def test_event_has_id_and_timestamp() -> None:
    e = Event(type="test", payload={"a": 1})
    assert e.event_id
    assert e.occurred_at


def test_bus_subscribers_receive_only_matching_type() -> None:
    bus = EventBus()
    received_a: list[Event] = []
    received_b: list[Event] = []
    bus.subscribe("a", received_a.append)
    bus.subscribe("b", received_b.append)
    bus.publish(Event(type="a", payload={}))
    bus.publish(Event(type="b", payload={}))
    bus.publish(Event(type="c", payload={}))
    assert len(received_a) == 1
    assert len(received_b) == 1


def test_outbox_drain_only_committed() -> None:
    out = OutboxRecorder()
    e1 = out.record(Event(type="x", payload={}))
    out.record(Event(type="x", payload={}))
    out.mark_committed(e1)
    drained = out.drain_committed()
    assert len(drained) == 1
    assert drained[0] is e1.event
    assert len(out._entries) == 1

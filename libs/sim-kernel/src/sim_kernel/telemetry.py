"""OpenTelemetry tracer and meter helpers, no-op by default.

sim-kernel stays free of I/O. We provide the import surface and the
no-op factory so services can opt in by setting OTEL_EXPORTER_OTLP_ENDPOINT.
When unset, get_tracer and get_meter return no-op tracers.
"""

from __future__ import annotations

import os

try:
    from opentelemetry import metrics, trace
except ImportError:  # pragma: no cover
    trace = None
    metrics = None


_TRACER_NAME = "santara.sim_kernel"
_METER_NAME = "santara.sim_kernel"


def _enabled() -> bool:
    return bool(os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT")) and trace is not None


def get_tracer(name: str = _TRACER_NAME):  # type: ignore[no-untyped-def]
    if not _enabled():
        return trace.get_tracer(name) if trace else _NoOpTracer()
    return trace.get_tracer(name)


def get_meter(name: str = _METER_NAME):  # type: ignore[no-untyped-def]
    if not _enabled():
        return metrics.get_meter(name) if metrics else _NoOpMeter()
    return metrics.get_meter(name)


class _NoOpTracer:
    def start_as_current_span(self, *_args: object, **_kwargs: object):  # type: ignore[no-untyped-def]
        return _NoOpSpan()


class _NoOpSpan:
    def __enter__(self) -> _NoOpSpan:
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def set_attribute(self, *_args: object, **_kwargs: object) -> None:
        return None


class _NoOpMeter:
    def create_counter(self, *_args: object, **_kwargs: object):  # type: ignore[no-untyped-def]
        return _NoOpCounter()

    def create_histogram(self, *_args: object, **_kwargs: object):  # type: ignore[no-untyped-def]
        return _NoOpHistogram()


class _NoOpCounter:
    def add(self, *_args: object, **_kwargs: object) -> None:
        return None


class _NoOpHistogram:
    def record(self, *_args: object, **_kwargs: object) -> None:
        return None

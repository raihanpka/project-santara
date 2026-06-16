"""Standard error slugs for Project Santara.

Services raise these (or subclasses) and the sim-gateway maps them to
gRPC status codes for cross-tier calls. They are kept in sim-kernel
so both Python and the Go service agree on the same slugs.
"""

from __future__ import annotations


class SantaraError(Exception):
    """Base error for Project Santara. Use a slug, not a free message."""

    slug: str = "santara_error"

    def __init__(self, message: str = "") -> None:
        super().__init__(message or self.slug)
        self.message = message or self.slug


class SimNotFoundError(SantaraError):
    slug = "sim_not_found"


class AgentNotFoundError(SantaraError):
    slug = "agent_not_found"


class InvalidArgumentError(SantaraError):
    slug = "invalid_argument"


class SimFailedError(SantaraError):
    slug = "sim_failed"


class TickLimitError(SantaraError):
    slug = "tick_limit_exceeded"

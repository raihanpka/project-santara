"""Project Santara shared library: domain models, events, errors, locales, protocol helpers.

This library contains no I/O. Every function is pure or accepts its
dependencies as arguments. Services that consume sim-kernel wire the
I/O at the edge; the library itself stays free of side effects.
"""

from sim_kernel.errors import (
    ErrAgentNotFound,
    ErrInvalidArgument,
    ErrSimFailed,
    ErrSimNotFound,
    ErrTickLimit,
)
from sim_kernel.events import Event, EventBus, OutboxEntry, OutboxRecorder
from sim_kernel.locales import LOCALES, Locale, get_locale
from sim_kernel.models import (
    Agent,
    AgentKind,
    Market,
    Region,
    Shock,
    ShockKind,
    Simulation,
    SimulationStatus,
)

__version__ = "0.1.0"

__all__ = [
    "Agent",
    "AgentKind",
    "ErrAgentNotFound",
    "ErrInvalidArgument",
    "ErrSimFailed",
    "ErrSimNotFound",
    "ErrTickLimit",
    "Event",
    "EventBus",
    "LOCALES",
    "Locale",
    "Market",
    "OutboxEntry",
    "OutboxRecorder",
    "Region",
    "Shock",
    "ShockKind",
    "Simulation",
    "SimulationStatus",
    "__version__",
    "get_locale",
]

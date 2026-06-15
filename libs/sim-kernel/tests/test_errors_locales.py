"""Tests for sim-kernel errors and locales."""

from __future__ import annotations

import pytest

from sim_kernel.errors import (
    ErrAgentNotFound,
    ErrInvalidArgument,
    ErrSimFailed,
    ErrSimNotFound,
    ErrTickLimit,
    SantaraError,
)
from sim_kernel.locales import LOCALES, get_locale


def test_error_slugs_are_stable() -> None:
    cases = [
        (ErrSimNotFound(), "sim_not_found"),
        (ErrAgentNotFound(), "agent_not_found"),
        (ErrInvalidArgument(), "invalid_argument"),
        (ErrSimFailed(), "sim_failed"),
        (ErrTickLimit(), "tick_limit_exceeded"),
    ]
    for err, expected_slug in cases:
        assert err.slug == expected_slug
        assert expected_slug in str(err)


def test_error_inherits_base() -> None:
    assert issubclass(ErrSimNotFound, SantaraError)
    assert issubclass(SantaraError, Exception)


def test_locales_known_set() -> None:
    assert set(LOCALES) == {"id", "us", "in", "ph"}


def test_get_locale_returns_dataclass() -> None:
    loc = get_locale("id")
    assert loc.currency_code == "IDR"
    assert loc.currency_symbol == "Rp"
    assert loc.format_money(15000) == "Rp 15,000"


def test_get_locale_unknown_raises() -> None:
    with pytest.raises(KeyError):
        get_locale("xx")

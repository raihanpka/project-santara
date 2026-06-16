"""Tests for sim-id-iklim climate emergency model."""

from __future__ import annotations

import pytest

from sim_id_iklim.anchor import CRISIS_THRESHOLD, ClimateEmergency


def test_low_values_no_crisis() -> None:
    engine = ClimateEmergency()
    result = engine.apply(hotspots=10, wind_speed_kmh=10, dry_days=5)
    assert result.haze_index == 5.0
    assert result.is_cross_border_crisis is False
    assert result.days_to_crisis > 0


def test_high_values_crisis() -> None:
    engine = ClimateEmergency()
    result = engine.apply(hotspots=50, wind_speed_kmh=20, dry_days=60)
    assert result.haze_index == 600.0
    assert result.is_cross_border_crisis is True
    assert result.days_to_crisis == 0


def test_boundary_just_below_threshold() -> None:
    engine = ClimateEmergency()
    # 50 * 20 * 50 / 100 = 500 (exactly at threshold, not a crisis since we use >)
    result = engine.apply(hotspots=50, wind_speed_kmh=20, dry_days=50)
    assert result.haze_index == 500.0
    assert result.is_cross_border_crisis is False


def test_zero_hotspots_never_crisis() -> None:
    engine = ClimateEmergency()
    result = engine.apply(hotspots=0, wind_speed_kmh=30, dry_days=30)
    assert result.haze_index == 0.0
    assert result.is_cross_border_crisis is False
    assert result.days_to_crisis == -1


def test_zero_wind_invalid() -> None:
    engine = ClimateEmergency()
    with pytest.raises(ValueError):
        engine.apply(hotspots=10, wind_speed_kmh=0, dry_days=5)


def test_negative_hotspots_invalid() -> None:
    engine = ClimateEmergency()
    with pytest.raises(ValueError):
        engine.apply(hotspots=-1, wind_speed_kmh=10, dry_days=5)


def test_negative_dry_days_invalid() -> None:
    engine = ClimateEmergency()
    with pytest.raises(ValueError):
        engine.apply(hotspots=10, wind_speed_kmh=10, dry_days=-1)


def test_scenario_always_karhutla_riau_haze() -> None:
    engine = ClimateEmergency()
    result = engine.apply(hotspots=10, wind_speed_kmh=10, dry_days=5)
    assert result.scenario == "karhutla_riau_haze"


def test_to_dict_matches_dataclass() -> None:
    engine = ClimateEmergency()
    result = engine.apply(hotspots=10, wind_speed_kmh=10, dry_days=5)
    d = result.to_dict()
    assert d["haze_index"] == result.haze_index
    assert d["is_cross_border_crisis"] == result.is_cross_border_crisis


def test_threshold_is_500() -> None:
    assert CRISIS_THRESHOLD == 500

"""Tests for sim-id-politik political dynamics model."""

from __future__ import annotations

import pytest

from sim_id_politik.anchor import PoliticalDynamics


def test_high_coverage_high_satisfaction_gain() -> None:
    engine = PoliticalDynamics()
    result = engine.apply(mbg_coverage_pct=80, satisfaction_score=70, base_swing_rate_pct=10)
    assert result.swing_change_pp == 5.6
    assert result.direction == "gain"
    assert result.confidence == "high"
    assert "5.60pp" in result.notes


def test_low_coverage_low_satisfaction_neutral() -> None:
    engine = PoliticalDynamics()
    result = engine.apply(mbg_coverage_pct=10, satisfaction_score=20, base_swing_rate_pct=5)
    assert result.swing_change_pp == 0.1
    assert result.direction == "neutral"
    assert result.confidence == "low"


def test_medium_coverage_medium_satisfaction_medium_confidence() -> None:
    engine = PoliticalDynamics()
    result = engine.apply(mbg_coverage_pct=50, satisfaction_score=50, base_swing_rate_pct=8)
    assert result.swing_change_pp == 2.0
    assert result.direction == "gain"
    assert result.confidence == "medium"


def test_zero_base_swing_invalid() -> None:
    engine = PoliticalDynamics()
    with pytest.raises(ValueError):
        engine.apply(mbg_coverage_pct=50, satisfaction_score=50, base_swing_rate_pct=0)


def test_coverage_above_100_invalid() -> None:
    engine = PoliticalDynamics()
    with pytest.raises(ValueError):
        engine.apply(mbg_coverage_pct=150, satisfaction_score=50, base_swing_rate_pct=10)


def test_satisfaction_negative_invalid() -> None:
    engine = PoliticalDynamics()
    with pytest.raises(ValueError):
        engine.apply(mbg_coverage_pct=50, satisfaction_score=-10, base_swing_rate_pct=10)


def test_scenario_always_mbg_swing_voter_2029() -> None:
    engine = PoliticalDynamics()
    result = engine.apply(mbg_coverage_pct=50, satisfaction_score=50, base_swing_rate_pct=10)
    assert result.scenario == "mbg_swing_voter_2029"


def test_to_dict_matches_dataclass() -> None:
    engine = PoliticalDynamics()
    result = engine.apply(mbg_coverage_pct=50, satisfaction_score=50, base_swing_rate_pct=10)
    d = result.to_dict()
    assert d["swing_change_pp"] == result.swing_change_pp
    assert d["direction"] == result.direction

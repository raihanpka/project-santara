"""Tests for the dataset loader."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pandas as pd
import pytest

from sim_id_fiskal.dataset import INDICATOR_FOR_FUEL, latest_fuel_price


def _write_fake_dataset(path: Path) -> None:
    """Write a tiny Parquet with one row per fuel."""
    rows = [
        {
            "date": "2026-06-01",
            "indicator": "PERTAMAX_IDR_PER_LITER",
            "region": "IDN",
            "value": 12500.0,
            "unit": "IDR_per_liter",
            "source_id": "esdm.pertamina.retail",
        },
        {
            "date": "2026-06-01",
            "indicator": "PERTALITE_IDR_PER_LITER",
            "region": "IDN",
            "value": 10000.0,
            "unit": "IDR_per_liter",
            "source_id": "esdm.pertamina.retail",
        },
        {
            "date": "2026-06-01",
            "indicator": "SOLAR_IDR_PER_LITER",
            "region": "IDN",
            "value": 6800.0,
            "unit": "IDR_per_liter",
            "source_id": "esdm.pertamina.retail",
        },
    ]
    pd.DataFrame(rows).to_parquet(path)


def test_latest_fuel_price_pertamax(tmp_path: Path) -> None:
    path = tmp_path / "fake.parquet"
    _write_fake_dataset(path)
    price = latest_fuel_price("pertamax", dataset_path=path)
    assert price.fuel == "pertamax"
    assert price.price_idr_per_liter == 12500.0
    assert price.as_of == date(2026, 6, 1)
    assert price.source_id == "esdm.pertamina.retail"


def test_latest_fuel_price_pertalite(tmp_path: Path) -> None:
    path = tmp_path / "fake.parquet"
    _write_fake_dataset(path)
    price = latest_fuel_price("pertalite", dataset_path=path)
    assert price.price_idr_per_liter == 10000.0


def test_latest_fuel_price_solar(tmp_path: Path) -> None:
    path = tmp_path / "fake.parquet"
    _write_fake_dataset(path)
    price = latest_fuel_price("solar", dataset_path=path)
    assert price.price_idr_per_liter == 6800.0


def test_latest_fuel_price_unknown_fuel_raises() -> None:
    with pytest.raises(KeyError):
        latest_fuel_price("avtur")


def test_latest_fuel_price_missing_file_raises(tmp_path: Path) -> None:
    path = tmp_path / "missing.parquet"
    with pytest.raises(FileNotFoundError):
        latest_fuel_price("pertamax", dataset_path=path)


def test_all_three_fuels_have_indicators() -> None:
    """Guard against typos in the fuel-to-indicator mapping."""
    assert set(INDICATOR_FOR_FUEL) == {"pertamax", "pertalite", "solar"}

"""Load the latest fuel prices from the curated dataset.

ponytail: single-purpose loader. Read-only access to the local
Parquet cache. No network calls at request time.

The loader reads from the local mirror of
raihanpka/indonesia-fiscal-pressure. For production, the Parquet
file is downloaded once during deployment and shipped as part
of the container image. At request time, the loader just opens
the local file and filters for the relevant indicator and
region.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path

import pandas as pd

# Default location is the dataset mirror bundled in the container.
DEFAULT_DATASET_PATH = Path(
    "/app/data/id_fiscal_pressure/dist/train-00000-of-00001.parquet"
)

# Fuel -> indicator name in the dataset. The fuel names are
# the public marketing names; the indicator names follow the
# long-format column in the curated Parquet.
INDICATOR_FOR_FUEL: dict[str, str] = {
    "pertamax": "PERTAMAX_IDR_PER_LITER",
    "pertalite": "PERTALITE_IDR_PER_LITER",
    "solar": "SOLAR_IDR_PER_LITER",
}

# Region for national-aggregate retail prices. Regional
# breakdowns are out of scope for v0.2.0.
REGION_NATIONAL = "IDN"


@dataclass(frozen=True)
class FuelPrice:
    fuel: str
    price_idr_per_liter: float
    as_of: date
    source_id: str

    def to_dict(self) -> dict:
        return {
            "fuel": self.fuel,
            "price_idr_per_liter": self.price_idr_per_liter,
            "as_of": self.as_of.isoformat(),
            "source_id": self.source_id,
        }


def latest_fuel_price(
    fuel: str,
    *,
    dataset_path: Path = DEFAULT_DATASET_PATH,
) -> FuelPrice:
    """Return the most recent national retail price for `fuel`.

    Raises:
      FileNotFoundError: if the dataset Parquet is not present
        (caller should fall back to caller-supplied price).
      KeyError: if `fuel` is not a recognised marketing name.
      ValueError: if no row exists for that fuel in the dataset.
    """
    indicator = INDICATOR_FOR_FUEL[fuel.lower()]
    df = pd.read_parquet(dataset_path)
    rows = df[
        (df["indicator"] == indicator)
        & (df["region"] == REGION_NATIONAL)
    ]
    if rows.empty:
        raise ValueError(
            f"No rows for indicator {indicator!r} in {dataset_path}"
        )
    latest = rows.sort_values("date", ascending=False).iloc[0]
    return FuelPrice(
        fuel=fuel.lower(),
        price_idr_per_liter=float(latest["value"]),
        as_of=date.fromisoformat(str(latest["date"])),
        source_id=str(latest["source_id"]),
    )

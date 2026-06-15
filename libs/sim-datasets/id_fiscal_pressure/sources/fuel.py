"""Curated Indonesian retail fuel (BBM) price history.

Indonesia does not publish a single structured historical retail price
table for BBM. Pertamina announces price changes on specific dates and
the press reports them. This module is a curated CSV that consolidates
those announcements into one source.

Coverage: 2014-11 to 2026-06. Sourced from news articles and the
Kabarbaik, IDN Times, Katadata, CNBC, Detik, ICCT, and Kompas coverage
of fuel prices. Each row in the source CSV cites a source_ref that
maps to a row in provenance.csv.

Fuel types included:
  PREMIUM             (subsidized, RON 88, ended 2020)
  PERTALITE           (subsidized, RON 90, from 2015)
  PERTAMAX            (non-subsidized, RON 92, from 1999)
  PERTAMAX_GREEN_95   (non-subsidized, RON 95, from 2023)
  PERTAMAX_TURBO      (non-subsidized, RON 98)
  SOLAR_SUBSIDI       (subsidized diesel, CN 48)
  BIOSOLAR            (subsidized biodiesel blend, same as Solar Subsidi)
  DEXLITE             (non-subsidized, CN 51)
  PERTAMINA_DEX       (non-subsidized, CN 53)
"""
from __future__ import annotations

import csv
from pathlib import Path

import pandas as pd

# Each row: (date, indicator, region, value, source_ref)
# Region codes: JAMALI (Java-Madura-Bali) or NASIONAL.
# Value is IDR per liter.
ROWS: list[tuple[str, str, str, int, str]] = [
    # 2014-2016 era, from CNBC Indonesia
    ("2014-11-18", "PREMIUM", "JAMALI", 8500, "CNBC-2022-09"),
    ("2014-11-18", "SOLAR_SUBSIDI", "JAMALI", 7250, "CNBC-2022-09"),
    ("2015-01-01", "PREMIUM", "JAMALI", 7600, "CNBC-2022-09"),
    ("2015-01-01", "SOLAR_SUBSIDI", "JAMALI", 7250, "CNBC-2022-09"),
    ("2015-01-19", "PREMIUM", "JAMALI", 6900, "CNBC-2022-09"),
    ("2015-01-19", "PREMIUM", "LUAR_JAMALI", 6700, "CNBC-2022-09"),
    ("2015-01-19", "SOLAR_SUBSIDI", "JAMALI", 6400, "CNBC-2022-09"),
    ("2015-01-19", "SOLAR_SUBSIDI", "LUAR_JAMALI", 6400, "CNBC-2022-09"),
    ("2015-03-01", "PREMIUM", "NASIONAL", 6800, "CNBC-2022-09"),
    ("2015-03-01", "SOLAR_SUBSIDI", "NASIONAL", 6400, "CNBC-2022-09"),
    ("2015-03-28", "PREMIUM", "NASIONAL", 7300, "CNBC-2022-09"),
    ("2015-03-28", "SOLAR_SUBSIDI", "NASIONAL", 6900, "CNBC-2022-09"),
    ("2015-07-24", "PERTALITE", "JAMALI", 8400, "Suara-2022-09"),
    ("2015-09-01", "PERTALITE", "JAMALI", 8300, "Suara-2022-09"),
    ("2016-01-01", "PREMIUM", "JAMALI", 7050, "CNBC-2022-09"),
    ("2016-01-01", "PREMIUM", "LUAR_JAMALI", 6950, "CNBC-2022-09"),
    ("2016-01-01", "SOLAR_SUBSIDI", "JAMALI", 5650, "CNBC-2022-09"),
    ("2016-01-01", "SOLAR_SUBSIDI", "LUAR_JAMALI", 5650, "CNBC-2022-09"),
    ("2016-01-01", "PERTALITE", "JAMALI", 7900, "Suara-2022-09"),
    ("2016-03-01", "PERTALITE", "JAMALI", 7500, "Suara-2022-09"),
    ("2016-04-01", "PREMIUM", "JAMALI", 6550, "CNBC-2022-09"),
    ("2016-04-01", "PREMIUM", "LUAR_JAMALI", 6450, "CNBC-2022-09"),
    ("2016-04-01", "SOLAR_SUBSIDI", "JAMALI", 5150, "CNBC-2022-09"),
    ("2016-04-01", "SOLAR_SUBSIDI", "LUAR_JAMALI", 5150, "CNBC-2022-09"),
    # 2017-2019, from Suara and Detik
    ("2017-01-01", "PERTALITE", "JAMALI", 7750, "Suara-2022-09"),
    ("2017-04-01", "PERTALITE", "JAMALI", 7900, "Suara-2022-09"),
    ("2018-01-20", "PERTALITE", "JAMALI", 7600, "JawaPos-2022-09"),
    ("2018-03-24", "PERTALITE", "JAMALI", 7800, "JawaPos-2022-09"),
    ("2019-01-05", "PERTALITE", "JAMALI", 7650, "JawaPos-2022-09"),
    # 2020-2021, stable
    ("2020-06-01", "PERTALITE", "JAMALI", 7650, "Kabarbaik-2026-06"),
    ("2020-06-01", "SOLAR_SUBSIDI", "JAMALI", 5150, "Kabarbaik-2026-06"),
    ("2021-06-01", "PERTALITE", "JAMALI", 7650, "Kabarbaik-2026-06"),
    ("2021-06-01", "SOLAR_SUBSIDI", "JAMALI", 5150, "Kabarbaik-2026-06"),
    # 2022, the big September jump
    ("2022-04-01", "PERTALITE", "JAMALI", 7650, "CNBC-2022-09"),
    ("2022-04-01", "PERTAMAX", "JAMALI", 12500, "CNBC-2022-09"),
    ("2022-04-01", "SOLAR_SUBSIDI", "JAMALI", 5150, "CNBC-2022-09"),
    ("2022-09-03", "PERTALITE", "JAMALI", 10000, "CNBC-2022-09"),
    ("2022-09-03", "PERTAMAX", "JAMALI", 14500, "CNBC-2022-09"),
    ("2022-09-03", "SOLAR_SUBSIDI", "JAMALI", 6800, "CNBC-2022-09"),
    ("2022-09-01", "PERTAMAX_TURBO", "JAMALI", 15900, "Suara-2022-09"),
    ("2022-09-01", "DEXLITE", "JAMALI", 17100, "Suara-2022-09"),
    ("2022-09-01", "PERTAMINA_DEX", "JAMALI", 17400, "Suara-2022-09"),
    # 2023 monthly non-subsidi, from Katadata
    ("2023-01-01", "PERTAMAX", "JAMALI", 12400, "Katadata-2023-10"),
    ("2023-03-01", "PERTAMAX", "JAMALI", 13300, "Katadata-2023-10"),
    ("2023-03-01", "DEXLITE", "JAMALI", 12650, "Katadata-2023-10"),
    ("2023-03-01", "PERTAMINA_DEX", "JAMALI", 13250, "Katadata-2023-10"),
    ("2023-05-01", "PERTAMAX", "JAMALI", 13300, "Katadata-2023-10"),
    ("2023-05-01", "PERTAMAX_TURBO", "JAMALI", 15000, "Katadata-2023-10"),
    ("2023-05-01", "DEXLITE", "JAMALI", 13700, "Katadata-2023-10"),
    ("2023-05-01", "PERTAMINA_DEX", "JAMALI", 14600, "Katadata-2023-10"),
    ("2023-06-01", "PERTAMAX_TURBO", "JAMALI", 15000, "Katadata-2023-10"),
    ("2023-06-01", "DEXLITE", "JAMALI", 14250, "Katadata-2023-10"),
    ("2023-06-01", "PERTAMINA_DEX", "JAMALI", 15400, "Katadata-2023-10"),
    ("2023-07-01", "PERTAMAX_TURBO", "JAMALI", 15100, "Katadata-2023-10"),
    ("2023-07-01", "DEXLITE", "JAMALI", 14950, "Katadata-2023-10"),
    ("2023-07-01", "PERTAMINA_DEX", "JAMALI", 15850, "Katadata-2023-10"),
    ("2023-08-01", "PERTAMAX_TURBO", "JAMALI", 14850, "Katadata-2023-10"),
    ("2023-08-01", "PERTAMINA_DEX", "JAMALI", 16850, "Katadata-2023-10"),
    ("2023-09-01", "PERTAMAX", "JAMALI", 13300, "Katadata-2023-10"),
    ("2023-09-01", "PERTAMAX_GREEN_95", "JAMALI", 15000, "Katadata-2023-10"),
    ("2023-09-01", "PERTAMAX_TURBO", "JAMALI", 15900, "Katadata-2023-10"),
    ("2023-09-01", "DEXLITE", "JAMALI", 16350, "Katadata-2023-10"),
    ("2023-09-01", "PERTAMINA_DEX", "JAMALI", 16900, "Katadata-2023-10"),
    ("2023-10-01", "PERTAMAX", "JAMALI", 14000, "Katadata-2023-10"),
    ("2023-10-01", "PERTAMAX_GREEN_95", "JAMALI", 16000, "Katadata-2023-10"),
    ("2023-10-01", "PERTAMAX_TURBO", "JAMALI", 16600, "Katadata-2023-10"),
    ("2023-10-01", "DEXLITE", "JAMALI", 17200, "Katadata-2023-10"),
    ("2023-10-01", "PERTAMINA_DEX", "JAMALI", 17900, "Katadata-2023-10"),
    # 2024-2025, mostly stable subsidized, non-subsidi moves
    ("2024-06-01", "PERTALITE", "JAMALI", 10000, "Kabarbaik-2026-06"),
    ("2024-06-01", "SOLAR_SUBSIDI", "JAMALI", 6800, "Kabarbaik-2026-06"),
    # 2026, from IDN Times and Kabarbaik
    ("2026-03-01", "PERTAMAX", "JAMALI", 12300, "IDNTimes-2026-06"),
    ("2026-03-01", "PERTAMAX_GREEN_95", "JAMALI", 12900, "IDNTimes-2026-06"),
    ("2026-03-01", "PERTAMAX_TURBO", "JAMALI", 13100, "IDNTimes-2026-06"),
    ("2026-03-01", "DEXLITE", "JAMALI", 14200, "IDNTimes-2026-06"),
    ("2026-03-01", "PERTAMINA_DEX", "JAMALI", 14500, "IDNTimes-2026-06"),
    ("2026-04-18", "PERTAMAX", "JAMALI", 12300, "IDNTimes-2026-06"),
    ("2026-04-18", "PERTAMAX_GREEN_95", "JAMALI", 12900, "IDNTimes-2026-06"),
    ("2026-04-18", "PERTAMAX_TURBO", "JAMALI", 19400, "IDNTimes-2026-06"),
    ("2026-04-18", "DEXLITE", "JAMALI", 23600, "IDNTimes-2026-06"),
    ("2026-04-18", "PERTAMINA_DEX", "JAMALI", 23900, "IDNTimes-2026-06"),
    ("2026-05-04", "PERTAMAX", "JAMALI", 12300, "IDNTimes-2026-06"),
    ("2026-05-04", "PERTAMAX_GREEN_95", "JAMALI", 12900, "IDNTimes-2026-06"),
    ("2026-05-04", "PERTAMAX_TURBO", "JAMALI", 19900, "IDNTimes-2026-06"),
    ("2026-05-04", "DEXLITE", "JAMALI", 26000, "IDNTimes-2026-06"),
    ("2026-05-04", "PERTAMINA_DEX", "JAMALI", 27900, "IDNTimes-2026-06"),
    ("2026-06-10", "PERTAMAX", "JAMALI", 16250, "IDNTimes-2026-06"),
    ("2026-06-10", "PERTAMAX_GREEN_95", "JAMALI", 17000, "IDNTimes-2026-06"),
    ("2026-06-10", "PERTAMAX_TURBO", "JAMALI", 19900, "IDNTimes-2026-06"),
    ("2026-06-10", "DEXLITE", "JAMALI", 26000, "IDNTimes-2026-06"),
    ("2026-06-10", "PERTAMINA_DEX", "JAMALI", 27900, "IDNTimes-2026-06"),
    # Biosolar is the same as Solar Subsidi (CN 48), record explicitly per agency naming
    ("2016-04-01", "BIOSOLAR", "JAMALI", 5150, "ICCT-2020-10"),
    ("2020-02-01", "BIOSOLAR", "JAMALI", 5150, "ICCT-2020-10"),
    ("2022-09-03", "BIOSOLAR", "JAMALI", 6800, "CNBC-2022-09"),
    ("2026-06-10", "BIOSOLAR", "JAMALI", 6800, "Kabarbaik-2026-06"),
]

UNIT = "IDR_per_liter"


def load_csv(path: str | Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    return df


def load_curated() -> pd.DataFrame:
    """Return the curated BBM price data as a long-format DataFrame."""
    rows: list[dict] = []
    for date, indicator, region, value, source_ref in ROWS:
        rows.append(
            {
                "date": date,
                "indicator": indicator,
                "region": region,
                "value": value,
                "unit": UNIT,
                "source_id": f"fuel.curated.{source_ref}",
            }
        )
    return pd.DataFrame(rows).reset_index(drop=True)


def write_csv(path: str | Path) -> None:
    """Write the curated data to a CSV for transparency."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["date", "indicator", "region", "value", "source_ref"])
        for row in ROWS:
            w.writerow(row)


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        write_csv(sys.argv[1])
    df = load_curated()
    print(df.head())
    print(
        f"rows={len(df)} date_range={df['date'].min()}..{df['date'].max()} "
        f"indicators={df['indicator'].nunique()}"
    )

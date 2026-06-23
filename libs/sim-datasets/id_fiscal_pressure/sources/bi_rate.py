"""Bank Indonesia 7-day reverse repo rate parser.

Source: BI-7Day-RR-by-BI-Web (user-provided).
The CSV is a clean long-format dump of the original XLSX.
Columns: no, tanggal, rate.
Tanggal is Indonesian date string like "21 Juli 2016".
Rate is a string like "5.25 %".
"""
from pathlib import Path

import pandas as pd

from ._dates import parse_id_date, parse_rate_pct

INDICATOR = "BI7DRR"
REGION = "IDN"
UNIT = "percent"
SOURCE_ID = "bi.web.7drr"


def load(path: str | Path) -> pd.DataFrame:
    """Return a long-format DataFrame with columns:
    date, indicator, region, value, unit, source_id.
    """
    df = pd.read_csv(path)
    df = df[["tanggal", "rate"]].dropna()
    df["date"] = df["tanggal"].apply(parse_id_date)
    df["value"] = df["rate"].apply(parse_rate_pct)
    out = pd.DataFrame(
        {
            "date": df["date"],
            "indicator": INDICATOR,
            "region": REGION,
            "value": df["value"],
            "unit": UNIT,
            "source_id": SOURCE_ID,
        }
    )
    return out.reset_index(drop=True)


if __name__ == "__main__":
    import sys

    src = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("raw/santara_bi_7day_rr.csv")
    df = load(src)
    print(df.head())
    print(f"rows={len(df)} date_range={df['date'].min()}..{df['date'].max()}")

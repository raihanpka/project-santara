"""Bank Indonesia 7-day reverse repo rate parser.

Source: BI-7Day-RR-by-BI-Web.xlsx (user-provided).
The file has 5 leading rows of title/header, then data starts.
Columns: NO, Tanggal, BI-7Day-RR.
Tanggal is Indonesian date string like "21 Juli 2016".
BI-7Day-RR is a string like "5.25 %".
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
    df = pd.read_excel(path, header=None)
    # The data block is everything after the header row containing NO, Tanggal, BI-7Day-RR.
    header_row = None
    for i, row in df.iterrows():
        vals = [str(v) for v in row.tolist()]
        if any("Tanggal" in v for v in vals) and any("BI-7Day" in v for v in vals):
            header_row = i
            break
    if header_row is None:
        raise ValueError(f"Could not find header row in {path}")
    data = df.iloc[header_row + 1 :].copy()
    data.columns = ["no", "tanggal", "rate", "extra"]
    data = data[["tanggal", "rate"]].dropna()
    data["date"] = data["tanggal"].apply(parse_id_date)
    data["value"] = data["rate"].apply(parse_rate_pct)
    out = pd.DataFrame(
        {
            "date": data["date"],
            "indicator": INDICATOR,
            "region": REGION,
            "value": data["value"],
            "unit": UNIT,
            "source_id": SOURCE_ID,
        }
    )
    return out.reset_index(drop=True)


if __name__ == "__main__":
    import sys

    src = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("raw/santara_bi_7day_rr.xlsx")
    df = load(src)
    print(df.head())
    print(f"rows={len(df)} date_range={df['date'].min()}..{df['date'].max()}")

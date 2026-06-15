"""Test provenance: every data row has a provenance row, in the same order."""
from __future__ import annotations

from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent.parent
DIST = HERE / "dist"


def test_row_counts_match() -> None:
    data = pd.read_parquet(DIST / "train-00000-of-00001.parquet")
    prov = pd.read_csv(DIST / "provenance.csv")
    assert len(data) == len(prov), (
        f"data has {len(data)} rows but provenance has {len(prov)} rows"
    )
    assert (data["row_id"].values == prov["row_id"].values).all(), "row_id mismatch"
    assert (data["source_id"].values == prov["source_id"].values).all(), "source_id mismatch"
    assert (data["date"].values == prov["date"].values).all(), "date mismatch"
    assert (data["indicator"].values == prov["indicator"].values).all(), "indicator mismatch"


def test_sources_csv_has_all_source_ids() -> None:
    data = pd.read_parquet(DIST / "train-00000-of-00001.parquet")
    sources = pd.read_csv(DIST / "sources.csv")
    used = set(data["source_id"].unique())
    registered_prefixes = set()
    for sid in sources["source_id"]:
        if sid.endswith(".*"):
            registered_prefixes.add(sid[:-1])
    # For each used source_id, either it is directly registered or
    # its prefix matches a wildcard.
    for sid in used:
        if sid in set(sources["source_id"]):
            continue
        if any(sid.startswith(p) for p in registered_prefixes):
            continue
        raise AssertionError(
            f"source_id {sid!r} used in data but not registered in sources.csv"
        )


def test_indicator_unit_consistent() -> None:
    data = pd.read_parquet(DIST / "train-00000-of-00001.parquet")
    grp = data.groupby("indicator")["unit"].nunique()
    inconsistent = grp[grp > 1]
    assert len(inconsistent) == 0, (
        f"Indicators with multiple units: {inconsistent.to_dict()}"
    )


def main() -> int:
    test_row_counts_match()
    print("[ok] row counts match")
    test_sources_csv_has_all_source_ids()
    print("[ok] all source_ids registered")
    test_indicator_unit_consistent()
    print("[ok] indicator -> unit is consistent")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

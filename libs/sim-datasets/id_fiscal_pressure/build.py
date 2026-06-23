"""Build the id_fiscal_pressure dataset.

Combines all sources into one long-format Parquet file plus a
provenance.csv and a dataset card. Validates row count and order
consistency between data and provenance.

Run from the package root:
    python -m libs.sim_datasets.id_fiscal_pressure.build

Outputs:
    dist/train-00000-of-00001.parquet   (long format, 6 columns)
    dist/provenance.csv                 (one row per data row)
    dist/README.md                      (dataset card, generated)
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent.parent))
sys.path.insert(0, str(HERE))

from sources import (  # noqa: E402
    bapanas,
    bi_rate,
    fuel,
)

RAW = HERE / "raw"
DIST = HERE / "dist"

CANONICAL_COLUMNS = ["date", "indicator", "region", "value", "unit", "source_id"]


def _row_index(df: pd.DataFrame) -> pd.DataFrame:
    """Add a stable row_id used by provenance.csv."""
    df = df.reset_index(drop=True).copy()
    df.insert(0, "row_id", df.index)
    return df


def load_jisdor_if_present() -> pd.DataFrame | None:
    path = RAW / "santara_jisdor.csv"
    if not path.exists():
        print("(skip) raw/santara_jisdor.csv not present (run sources/jisdor.py to fetch)")
        return None
    df = pd.read_csv(path)
    df = df.rename(columns={"jual": "value"})
    df["indicator"] = "USDIDR_JISDOR"
    df["region"] = "IDN"
    df["unit"] = "IDR_per_USD"
    out = df[["date", "indicator", "region", "value", "unit"]].copy()
    out["source_id"] = "bi.ws.jisdor"
    out["value"] = out["value"].astype(float)
    return out[CANONICAL_COLUMNS]


def load_pihps(path: Path) -> pd.DataFrame:
    """Load the combined PIHPS CSV (pihps.daily.* and pihps.api.*).
    The file is already in canonical long format.
    """
    df = pd.read_csv(path)
    return df[CANONICAL_COLUMNS]


def load_all() -> pd.DataFrame:
    pieces: list[pd.DataFrame] = []
    print("Loading santara_bi_7day_rr.csv ...")
    pieces.append(bi_rate.load(RAW / "santara_bi_7day_rr.csv"))
    print("Loading santara_pihps.csv ...")
    pieces.append(load_pihps(RAW / "santara_pihps.csv"))
    print("Loading santara_bapanas_konsumen.csv ...")
    pieces.append(bapanas.load(RAW / "santara_bapanas_konsumen.csv"))
    print("Loading fuel curated ...")
    pieces.append(fuel.load_curated())
    j = load_jisdor_if_present()
    if j is not None:
        pieces.append(j)
    combined = pd.concat(pieces, ignore_index=True)
    combined["date"] = combined["date"].astype(str)
    combined["value"] = combined["value"].astype(float)
    return combined[CANONICAL_COLUMNS].sort_values(
        ["source_id", "date", "indicator", "region"]
    ).reset_index(drop=True)


# Source registry: source_id -> provenance metadata
# These are the "macro" entries, one per source. The provenance.csv
# uses these plus per-row fetcher records for the JISDOR SOAP loop.
SOURCE_REGISTRY: dict[str, dict[str, str]] = {
    "bi.web.7drr": {
        "title": "BI 7-Day Reverse Repo Rate (BI-Rate)",
        "publisher": "Bank Indonesia",
        "url": "https://www.bi.go.id/id/statistik/indikator/bi-rate.aspx",
        "license": "Public domain (Indonesian government open data)",
        "notes": "User-provided XLSX, scraped from BI web page, 129 monthly observations 2016-2026.",
    },
    "bi.ws.jisdor": {
        "title": "JISDOR USD/IDR Reference Rate",
        "publisher": "Bank Indonesia",
        "url": "https://www.bi.go.id/biwebservice/wskursbi.asmx?op=getSubKursJisdor3",
        "license": "Public domain (Indonesian government open data)",
        "notes": "Pulled via BI SOAP web service; one fetch per calendar month, then deduplicated.",
    },
    "pihps.daily.*": {
        "title": "Indonesian Food Prices Daily (azzandwi1 mirror of PIHPS)",
        "publisher": "Bank Indonesia PIHPS, curated by azzandwi1",
        "url": "https://github.com/azzandwi1/indonesian-food-prices-dataset",
        "license": "Public domain (PIHPS) / unspecified (curation)",
        "notes": "Daily national average consumer food prices, 2018-01-01 to 2021-12-31. Used directly as a source for the 2018-2021 range.",
    },
    "pihps.api.*": {
        "title": "PIHPS Histogram Data JSON API",
        "publisher": "Bank Indonesia",
        "url": "https://www.bi.go.id/hargapangan/WebSite/Home/GetHistogramData",
        "license": "Public domain (Indonesian government open data)",
        "notes": "Backfill for 2022 to present. Sampled at weekly cadence for 10 core commodities. National average taken from the SemuaProvinsi field in the response.",
    },
    "bapanas.bulanan.*": {
        "title": "Rata-rata Harga Pangan Bulanan Tingkat Konsumen Nasional",
        "publisher": "Badan Pangan Nasional (Bapanas)",
        "url": "https://data.badanpangan.go.id/datasetpublications/cx8/rata-rata-harga-pangan-bulanan-konsumen-nasional",
        "license": "Public domain (Indonesian government open data)",
        "notes": "Monthly national consumer food prices, 2021-01 to 2025-12. Last published update is December 2025.",
    },
    "fuel.curated.*": {
        "title": "Curated Indonesian retail fuel (BBM) price history",
        "publisher": "Project Santara curation from public news sources",
        "url": "various (see per-row source_ref)",
        "license": "Public domain (news reporting)",
        "notes": "Curated from CNBC Indonesia, Detik, Suara, JawaPos, ICCT, Katadata, IDN Times, Kabarbaik, Kompas. Not from a single structured source. Each row carries a source_ref tag.",
    },
}

ARTICLE_REFS: dict[str, dict[str, str]] = {
    "CNBC-2022-09": {
        "title": "Jejak Harga BBM RI: Dulu Pernah Seharga Rp 0,3 per Liter",
        "publisher": "CNBC Indonesia",
        "url": "https://www.cnbcindonesia.com/market/20220905074943-17-369212/jejak-harga-bbm-ri-dulu-pernah-seharga-rp-03-per-liter",
        "fetched": "2026-06-15",
    },
    "Suara-2022-09": {
        "title": "Perjalanan Harga Pertalite dari Tahun 2015 Sampai Sekarang",
        "publisher": "Suara.com",
        "url": "https://www.suara.com/bisnis/2022/09/02/151421/perjalanan-harga-pertalite-dari-tahun-2015-sampai-sekarang",
        "fetched": "2026-06-15",
    },
    "JawaPos-2022-09": {
        "title": "Berikut Fluktuasi Harga BBM Bersubsidi Dalam 10 Tahun Terakhir",
        "publisher": "JawaPos",
        "url": "https://www.jawapos.com/ekonomi/2209030078/berikut-fluktuasi-harga-bbm-bersubsidi-dalam-10-tahun-terakhir",
        "fetched": "2026-06-15",
    },
    "ICCT-2020-10": {
        "title": "The retail fuels market in Indonesia",
        "publisher": "International Council on Clean Transportation",
        "url": "https://theicct.org/wp-content/uploads/2021/06/Retail-fuels-indonesia-oct2020.pdf",
        "fetched": "2026-06-15",
    },
    "Katadata-2023-10": {
        "title": "Rekam Jejak Fluktuasi Harga BBM Non Subsidi Pertamina Sepanjang 2023",
        "publisher": "Katadata",
        "url": "https://katadata.co.id/berita/energi/651a60e603a96/rekam-jejak-fluktuasi-harga-bbm-non-subsidi-pertamina-sepanjang-2023",
        "fetched": "2026-06-15",
    },
    "IDNTimes-2026-06": {
        "title": "Riwayat Harga BBM di Indonesia dari Masa ke Masa, Naik Turun!",
        "publisher": "IDN Times",
        "url": "https://www.idntimes.com/business/economy/riwayat-harga-bbm-di-indonesia-dari-masa-ke-masa-q9t01-00-s5qpm-gl267k",
        "fetched": "2026-06-15",
    },
    "Kabarbaik-2026-06": {
        "title": "Harga BBM dari Masa ke Masa: Catatan Fluktuasi Subsidi Sejak Orde Lama hingga Sekarang",
        "publisher": "Kabarbaik",
        "url": "https://kabarbaik.co/harga-bbm-dari-masa-ke-masa-catatan-fluktuasi-subsidi-sejak-orde-lama-hingga-sekarang/",
        "fetched": "2026-06-15",
    },
    "Kompas-2026-06": {
        "title": "Dulu Pertamax Pernah Rp 5.000 Per Liter, Begini Perjalanannya Sejak Diluncurkan 1999",
        "publisher": "Kompas",
        "url": "https://www.kompas.com/stori/read/2026/06/11/151307079/dulu-pertamax-pernah-rp-5000-per-liter-begini-perjalanannya-sejak",
        "fetched": "2026-06-15",
    },
}


def write_provenance(df: pd.DataFrame, dist: Path) -> None:
    """Write provenance.csv: one row per data row, with source reference."""
    df = _row_index(df)
    sources = []
    for sid, meta in SOURCE_REGISTRY.items():
        sources.append({"source_id": sid, **meta})
    sources_df = pd.DataFrame(sources)
    sources_df.to_csv(dist / "sources.csv", index=False)

    # Per-row provenance: each row in df gets its source_id's metadata,
    # plus a source_ref column for curated sources.
    rows = []
    for _, r in df.iterrows():
        sid = r["source_id"]
        # Find the registry entry (handle wildcard 'pihps.daily.*' etc)
        if sid in SOURCE_REGISTRY:
            meta = SOURCE_REGISTRY[sid]
        else:
            # Try prefix match for wildcard entries
            meta = None
            for key, val in SOURCE_REGISTRY.items():
                if key.endswith(".*") and sid.startswith(key[:-1]):
                    meta = val
                    break
            if meta is None:
                meta = {"title": "unknown", "publisher": "unknown", "url": "", "license": "", "notes": ""}
        # For curated fuel, add the source_ref article
        source_ref_url = ""
        if sid.startswith("fuel.curated."):
            ref_tag = sid.replace("fuel.curated.", "")
            article = ARTICLE_REFS.get(ref_tag)
            if article:
                source_ref_url = article["url"]
        rows.append(
            {
                "row_id": int(r["row_id"]),
                "date": r["date"],
                "indicator": r["indicator"],
                "region": r["region"],
                "value": r["value"],
                "unit": r["unit"],
                "source_id": sid,
                "source_title": meta["title"],
                "source_publisher": meta["publisher"],
                "source_url": meta["url"],
                "source_license": meta["license"],
                "source_ref_url": source_ref_url,
                "notes": meta["notes"],
            }
        )
    out = pd.DataFrame(rows)
    out.to_csv(dist / "provenance.csv", index=False)
    print(f"[write] {dist / 'provenance.csv'} rows={len(out)}")


def write_parquet(df: pd.DataFrame, dist: Path) -> None:
    """Write the combined Parquet. Only canonical columns (no row_id) so the HF dataset viewer renders correctly."""
    out = df[CANONICAL_COLUMNS].copy()
    out["date"] = pd.to_datetime(out["date"])
    out.to_parquet(dist / "train-00000-of-00001.parquet", index=False)
    print(f"Wrote {dist / 'train-00000-of-00001.parquet'} ({len(out)} rows)")


def write_csv(df: pd.DataFrame, dist: Path) -> None:
    """Also write a CSV copy so users without Parquet tooling can load it."""
    out = _row_index(df)
    out = out[["row_id"] + CANONICAL_COLUMNS]
    data_dir = dist / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    out.to_csv(data_dir / "santara_fiscal_pressure_long.csv", index=False)
    print(f"Wrote {data_dir / 'santara_fiscal_pressure_long.csv'} ({len(out)} rows)")


def copy_raw_csvs(dist: Path) -> None:
    """Copy the per-source raw CSVs into dist/ for full transparency."""
    data_dir = dist / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    for src in [
        "santara_bapanas_konsumen.csv",
        "santara_bi_7day_rr.csv",
        "santara_pihps.csv",
        "santara_jisdor.csv",
    ]:
        src_path = RAW / src
        if src_path.exists():
            target = data_dir / src
            target.write_bytes(src_path.read_bytes())
            print(f"Copied raw {src} to {target}")


SOURCE_FAMILY_TO_FILE: dict[str, str] = {
    "bi.web": "bi_rate",
    "bi.ws": "jisdor",
    "pihps.daily": "pihps_daily",
    "pihps.api": "pihps_api",
    "bapanas.bulanan": "bapanas",
    "fuel.curated": "fuel_curated",
}


def write_per_source_parquet(df: pd.DataFrame, dist: Path) -> None:
    """Write one Parquet per source family at dist/ root."""
    df = df.copy()
    df["source_family"] = df["source_id"].str.split(".").str[:2].str.join(".")
    for family, stem in SOURCE_FAMILY_TO_FILE.items():
        subset = df[df["source_family"] == family]
        if subset.empty:
            print(f"[skip] no rows for {family} ({stem}.parquet not written)")
            continue
        out = subset[CANONICAL_COLUMNS].copy()
        out["date"] = pd.to_datetime(out["date"])
        path = dist / f"{stem}.parquet"
        out.to_parquet(path, index=False)
        print(f"Wrote {path} ({len(out)} rows)")


def main() -> int:
    DIST.mkdir(parents=True, exist_ok=True)

    df = load_all()
    print(f"\nTotal rows after combine: {len(df)}")
    write_parquet(df, DIST)
    write_per_source_parquet(df, DIST)
    write_csv(df, DIST)
    copy_raw_csvs(DIST)
    write_provenance(df, DIST)

    readme = DIST / "README.md"
    if readme.exists():
        print(f"Preserving existing card at {readme} (hand-curated)")
    else:
        print("No README at {}. Write one before pushing to HF.".format(readme))

    print("\nSummary:")
    print(f"  Total rows: {len(df)}")
    print(f"  Date range: {df['date'].min()} to {df['date'].max()}")
    print(f"  Distinct indicators: {df['indicator'].nunique()}")
    print("  By source_id:")
    for sid, n in df["source_id"].value_counts().items():
        print(f"    {sid}: {n}")
    print("\nBuild complete. Files in dist/:")
    print("  train-00000-of-00001.parquet")
    for stem in SOURCE_FAMILY_TO_FILE.values():
        print(f"  {stem}.parquet")
    print("  provenance.csv")
    print("  sources.csv")
    print("  data/ (raw per-source copies)")
    return 0


if __name__ == "__main__":
    sys.exit(main())

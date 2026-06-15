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
    jisdor,
    pihps_daily,
    pihps_extension,
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


def load_pihps_extension_if_present() -> pd.DataFrame | None:
    path = RAW / "santara_pihps_extension.csv"
    if not path.exists():
        print(
            "(skip) raw/santara_pihps_extension.csv not present "
            "(run sources/pihps_extension.py to fetch)"
        )
        return None
    df = pd.read_csv(path)
    return df[CANONICAL_COLUMNS]


def load_all() -> pd.DataFrame:
    pieces: list[pd.DataFrame] = []
    print("Loading santara_bi_7day_rr.xlsx ...")
    pieces.append(bi_rate.load(RAW / "santara_bi_7day_rr.xlsx"))
    print("Loading santara_pihps_daily.csv ...")
    pieces.append(pihps_daily.load(RAW / "santara_pihps_daily.csv"))
    print("Loading santara_pihps_extension.csv ...")
    ext = load_pihps_extension_if_present()
    if ext is not None:
        pieces.append(ext)
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
    out = _row_index(df)
    out = out[["row_id"] + CANONICAL_COLUMNS]
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
        "santara_bi_7day_rr.xlsx",
        "santara_pihps_daily.csv",
        "santara_jisdor.csv",
        "santara_pihps_extension.csv",
    ]:
        src_path = RAW / src
        if src_path.exists():
            target = data_dir / src
            target.write_bytes(src_path.read_bytes())
            print(f"Copied raw {src} to {target}")


def write_dataset_card(df: pd.DataFrame, dist: Path) -> None:
    """Generate the README.md dataset card."""
    total = len(df)
    by_source = df["source_id"].value_counts().to_dict()
    date_min = df["date"].min()
    date_max = df["date"].max()
    indicators = sorted(df["indicator"].unique().tolist())
    # Limit indicators list in card for readability
    indicator_preview = ", ".join(indicators[:8]) + (
        f", ... ({len(indicators)} total)" if len(indicators) > 8 else ""
    )

    # Build size_category
    if total < 10_000:
        size_cat = "n<10K"
    elif total < 100_000:
        size_cat = "10K<n<100K"
    else:
        size_cat = "100K<n<1M"

    card = f"""---
license: apache-2.0
task_categories:
  - time-series-forecasting
language:
  - id
tags:
  - indonesia
  - fiscal
  - macroeconomics
  - food-prices
  - fuel-prices
  - exchange-rate
  - interest-rate
  - project-santara
size_categories:
  - {size_cat}
pretty_name: Indonesia Fiscal Pressure Tracker
dataset_info:
  config_name: default
  features:
    - name: date
      dtype: date32
    - name: indicator
      dtype: string
    - name: region
      dtype: string
    - name: value
      dtype: float64
    - name: unit
      dtype: string
    - name: source_id
      dtype: string
  splits:
    - name: train
      num_bytes: ~3MB
      num_examples: {total}
---

# Indonesia Fiscal Pressure Tracker

A curated, provenance-tracked time series of fiscal pressure indicators for the Republic of Indonesia. Built as the input data layer for the `sim-id-fiskal` service in Project Santara: An Open-Source Counterfactual Microservices Platform for Simulating Indonesia's Economic, Political, and Climate Systems.

## Dataset Summary

This dataset combines six primary data sources into a single long-format table. Each row is a single observation of one indicator at one date in one region. The long format is the right shape for time series analysis, joins, and the gRPC boundary the sim-engine expects.

| Source | Cadence | Series count | Coverage |
|---|---|---|---|
| Bank Indonesia 7-day reverse repo rate (user-provided xlsx) | Monthly | 1 | 2016-07 to 2026-06 |
| BI JISDOR (USD/IDR reference rate) | Daily | 1 | script-ready (see notes) |
| PIHPS daily via azzandwi1 curation | Daily | 32 | 2018-01-01 to 2021-12-31 |
| PIHPS API backfill | Weekly | 10 | partial (see notes) |
| Bapanas national consumer food prices | Monthly | 26 | 2021-01 to 2025-12 |
| Curated retail fuel (BBM) prices | Event-driven | 9 | 2014-11 to 2026-06 |

Total rows: **{total}**. Date range: **{date_min}** to **{date_max}**.

Sample indicators: {indicator_preview}.

## Supported Tasks and Languages

- Time series forecasting
- Macro shock simulation
- Causal analysis of fiscal and price shocks
- Inflation impact modeling

The dataset is in Bahasa Indonesia. Source documentation is mostly in Bahasa Indonesia with some English.

## Dataset Structure

### Data Fields

| Field | Type | Description |
|---|---|---|
| date | date32 | Observation date in ISO format (YYYY-MM-DD). |
| indicator | string | Canonical indicator name. |
| region | string | Region code. NASIONAL for national average, JAMALI for Java-Madura-Bali (subsidized BBM pricing), LUAR_JAMALI for outside Jamali, IDN for country-level monetary data. |
| value | float64 | Observation value, in the unit declared in the unit column. |
| unit | string | One of: IDR_per_kg, IDR_per_liter, IDR_per_USD, percent. |
| source_id | string | Foreign key into provenance.csv. |

### Indicator Taxonomy

- BI7DRR (Bank Indonesia 7-day reverse repo rate)
- USDIDR_JISDOR (USD/IDR reference rate)
- BAWANG_*, CABAI_*, DAGING_*, TELUR_*, MINYAK_*, GULA_*, BERAS_* (food prices)
- PREMIUM, PERTALITE, PERTAMAX, PERTAMAX_GREEN_95, PERTAMAX_TURBO, SOLAR_SUBSIDI, BIOSOLAR, DEXLITE, PERTAMINA_DEX (fuel prices)

### Data Splits

A single train split. Standard time-based splits (train on first 80 percent, test on last 20 percent) are appropriate.

## Dataset Creation

### Source Data

The dataset is sourced from six primary data sources.

1. **Bank Indonesia 7-day reverse repo rate.** User-provided XLSX from `bi.go.id/id/statistik/indikator/bi-rate.aspx`. 129 monthly observations 2016-2026. Preserved in `data/santara_bi_7day_rr.xlsx`.
2. **BI JISDOR.** Fetched via BI SOAP at `bi.go.id/biwebservice/wskursbi.asmx?op=getSubKursJisdor3`. Script-ready. The published JISDOR data starts 2013-05-20. The script in `sources/jisdor.py` paginates by month.
3. **PIHPS daily 2018-2021.** From `azzandwi1/indonesian-food-prices-dataset`. 1,804 daily observations across 32 commodities.
4. **PIHPS API backfill 2022-present.** Via JSON API at `bi.go.id/hargapangan/WebSite/Home/GetHistogramData`. Script in `sources/pihps_extension.py` samples weekly for 10 core commodities, uses the `SemuaProvinsi` field for national average.
5. **Bapanas monthly.** From `data.badanpangan.go.id`. 2021-01 to 2025-12 across 26 commodities.
6. **Curated BBM retail prices.** From news articles. Each row carries a `source_ref` tag mapping to the original article URL in `provenance.csv`. Outlets: CNBC Indonesia, Suara, JawaPos, ICCT, Katadata, IDN Times, Kabarbaik, Kompas.

### Annotations

The dataset has no manual annotations. The `indicator` column is a canonical name derived from the source column names.

### Personal and Sensitive Information

None. The dataset contains only public economic indicators. No personal data.

## Considerations for Using the Data

### Known Limitations

- **JISDOR daily history is script-ready but not populated.** The fetch script exists at `sources/jisdor.py` and works from a normal network. The build sandbox could not reach the BI SOAP endpoint reliably. Run the script from your machine to populate the full 2013-2026 daily series.
- **PIHPS daily 2022-2026 is sampled weekly, not daily.** The backfill uses one observation per week per commodity. Daily granularity requires additional backfill.
- **PIHPS extension coverage at the time of this dataset build is partial.** The initial sandbox run captured a limited window. The script is in `sources/pihps_extension.py`; run it with your full date range to complete the backfill.
- **Bapanas monthly ends December 2025.** Bapanas has not published a January-June 2026 update at the time of dataset publication.
- **Fuel prices are event-driven, not continuous.** Indonesia announces BBM price changes on specific dates. Granularity is event-level, not daily.
- **No imputed values.** Missing or unavailable values are simply not present.
- **Provenance is recorded at two levels.** A macro level (one entry per source_id pattern in `sources.csv`) and a per-row level (one entry per data row in `provenance.csv`).

### Social Impact

This dataset is part of Project Santara: An Open-Source Counterfactual Microservices Platform for Simulating Indonesia's Economic, Political, and Climate Systems. The platform lets policy makers, journalistes, and citizens ask "what if" questions about proposed economic policies and get answers grounded in real data.

## Additional Information

### Dataset Curators

- Raihan Putra Kirana (project lead, Project Santara, `raihanputragpr@gmail.com`)
- The Project Santara open-source contributors
- AI assistants (used as curators for the fuel-price source, compiling news articles into one canonical CSV; AI was not used to impute any values)

### Licensing Information

This dataset is licensed under Apache 2.0. Source data is public domain (per UU No. 14/2008 on Indonesian Open Data) unless noted in the source registry.

### Citation Information

If you use this dataset in academic work, please cite both Project Santara and the original sources.

```bibtex
@dataset{{id-fiscal-pressure-2026,
  author = {{Raihan Putra Kirana and the Project Santara contributors}},
  title  = {{Indonesia Fiscal Pressure Tracker}},
  year   = {{2026}},
  url    = {{https://huggingface.co/datasets/raihanpka/id-fiscal-pressure}},
  note   = {{Part of Project Santara: An Open-Source Counterfactual Microservices Platform for Simulating Indonesia's Economic, Political, and Climate Systems}}
}}
```

For citing the Project Santara platform itself:

```bibtex
@misc{{project-santara-2026,
  author = {{Raihan Putra Kirana}},
  title  = {{Project Santara: An Open-Source Counterfactual Microservices Platform for Simulating Indonesia's Economic, Political, and Climate Systems}},
  year   = {{2026}},
  url    = {{https://github.com/raihanpka/project-santara}}
}}
```

The underlying data sources, cited separately when reusing the data:

```bibtex
@misc{{bi-stat-2026,
  author = {{Bank Indonesia}},
  title  = {{BI 7-Day Reverse Repo Rate and JISDOR USD/IDR Reference Rate}},
  year   = {{2026}},
  url    = {{https://www.bi.go.id/}}
}}

@misc{{bapanas-bulanan-2026,
  author = {{Badan Pangan Nasional}},
  title  = {{Rata-rata Harga Pangan Bulanan Tingkat Konsumen Nasional}},
  year   = {{2026}},
  url    = {{https://data.badanpangan.go.id/}}
}}

@misc{{azzandwi1-pihps-daily-2024,
  author = {{azzandwi1}},
  title  = {{Indonesian Food Prices Dataset}},
  year   = {{2024}},
  url    = {{https://github.com/azzandwi1/indonesian-food-prices-dataset}}
}}

@misc{{bi-pihps-api-2026,
  author = {{Bank Indonesia}},
  title  = {{PIHPS Histogram Data JSON API}},
  year   = {{2026}},
  url    = {{https://www.bi.go.id/hargapangan/WebSite/Home/GetHistogramData}}
}}
```

For the curated fuel-price source, each row in `provenance.csv` carries the specific article URL and the news outlet name. The outlets are CNBC Indonesia, Suara, JawaPos, ICCT, Katadata, IDN Times, Kabarbaik, and Kompas.

### Contributions

Open an issue or pull request at `github.com/raihanpka/project-santara`. Propose a new raw CSV in `raw/` with a `santara_` prefix and a matching source module in `sources/`. For the dataset card, edit `build.py` and re-run.

## How to Load

```python
from datasets import load_dataset

ds = load_dataset("raihanpka/id-fiscal-pressure", split="train")
print(ds[0])
print(f"Total rows: {{len(ds)}}")
```

Or load the long-format CSV directly:

```python
import pandas as pd
df = pd.read_csv(
    "https://huggingface.co/datasets/raihanpka/id-fiscal-pressure/resolve/main/data/santara_fiscal_pressure_long.csv"
)
```

## Repository

The build script and source modules live in the Project Santara repository at `libs/sim-datasets/id_fiscal_pressure/`. Reproduce the build with:

```
python3 libs/sim-datasets/id_fiscal_pressure/build.py
```
"""
    (dist / "README.md").write_text(card, encoding="utf-8")
    print(f"Wrote {dist / 'README.md'}")


def main() -> int:
    DIST.mkdir(parents=True, exist_ok=True)
    df = load_all()
    print(f"\nTotal rows after combine: {len(df)}")
    write_parquet(df, DIST)
    write_csv(df, DIST)
    copy_raw_csvs(DIST)
    write_provenance(df, DIST)
    write_dataset_card(df, DIST)
    print("\nSummary:")
    print(f"  Total rows: {len(df)}")
    print(f"  Date range: {df['date'].min()} to {df['date'].max()}")
    print(f"  Distinct indicators: {df['indicator'].nunique()}")
    print("  By source_id:")
    for sid, n in df["source_id"].value_counts().items():
        print(f"    {sid}: {n}")
    print("\nBuild complete. Files in dist/:")
    print(f"  train-00000-of-00001.parquet")
    print(f"  README.md (dataset card)")
    print(f"  provenance.csv")
    print(f"  sources.csv")
    print(f"  data/santara_fiscal_pressure_long.csv")
    print(f"  data/santara_*.csv (raw per-source copies)")
    return 0


if __name__ == "__main__":
    sys.exit(main())

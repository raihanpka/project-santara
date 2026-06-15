"""PIHPS daily national consumer food prices.

Source: azzandwi1/indonesian-food-prices-dataset (raw_data/daily.csv).
Date range: 2018-01-01 to 2021-12-31 (4 years).
32 columns of commodity prices in IDR per unit.
Date format in source: 'DD/ MM/ YYYY' (e.g. '01/ 01/ 2018').

Gap: 2022-01-01 to present. The PIHPS page is JavaScript-rendered and
has no public API. The Bapanas monthly CSV covers 2021-2025 as a
fallback. For daily 2022-2026 you will need to backfill manually.
"""
from pathlib import Path

import pandas as pd

from ._dates import parse_pihps_date

# Mapping from azzandwi1 CSV column to canonical (indicator, unit, source_id)
COLUMN_MAP: dict[str, tuple[str, str, str]] = {
    "beras": ("BERAS_PREMIUM_NASIONAL", "IDR_per_kg", "pihps.daily.beras"),
    "beras_kb1": ("BERAS_KUALITAS_BAWAH_1", "IDR_per_kg", "pihps.daily.beras_kb1"),
    "beras_kb2": ("BERAS_KUALITAS_BAWAH_2", "IDR_per_kg", "pihps.daily.beras_kb2"),
    "beras_km1": ("BERAS_KUALITAS_MEDIUM_1", "IDR_per_kg", "pihps.daily.beras_km1"),
    "beras_km2": ("BERAS_KUALITAS_MEDIUM_2", "IDR_per_kg", "pihps.daily.beras_km2"),
    "beras_ks1": ("BERAS_KUALITAS_SUPER_1", "IDR_per_kg", "pihps.daily.beras_ks1"),
    "beras_ks2": ("BERAS_KUALITAS_SUPER_2", "IDR_per_kg", "pihps.daily.beras_ks2"),
    "daging_ayam": ("DAGING_AYAM_RATA_RATA", "IDR_per_kg", "pihps.daily.daging_ayam"),
    "daging_ayam_rs": ("DAGING_AYAM_RAS_SEGAR", "IDR_per_kg", "pihps.daily.daging_ayam_rs"),
    "daging_sapi": ("DAGING_SAPI_RATA_RATA", "IDR_per_kg", "pihps.daily.daging_sapi"),
    "daging_sapi_k1": ("DAGING_SAPI_KUALITAS_1", "IDR_per_kg", "pihps.daily.daging_sapi_k1"),
    "daging_sapi_k2": ("DAGING_SAPI_KUALITAS_2", "IDR_per_kg", "pihps.daily.daging_sapi_k2"),
    "telur_ayam": ("TELUR_AYAM_RATA_RATA", "IDR_per_kg", "pihps.daily.telur_ayam"),
    "telur_ayam_rs": ("TELUR_AYAM_RAS_SEGAR", "IDR_per_kg", "pihps.daily.telur_ayam_rs"),
    "bawang_merah": ("BAWANG_MERAH_RATA_RATA", "IDR_per_kg", "pihps.daily.bawang_merah"),
    "bawang_merah_sedang": (
        "BAWANG_MERAH_UKURAN_SEDANG", "IDR_per_kg", "pihps.daily.bawang_merah_sedang"
    ),
    "bawang_putih": ("BAWANG_PUTIH_RATA_RATA", "IDR_per_kg", "pihps.daily.bawang_putih"),
    "bawang_putih_sedang": (
        "BAWANG_PUTIH_UKURAN_SEDANG", "IDR_per_kg", "pihps.daily.bawang_putih_sedang"
    ),
    "cabai_merah": ("CABAI_MERAH_RATA_RATA", "IDR_per_kg", "pihps.daily.cabai_merah"),
    "cabai_merah_besar": ("CABAI_MERAH_BESAR", "IDR_per_kg", "pihps.daily.cabai_merah_besar"),
    "cabai_merah_keriting": (
        "CABAI_MERAH_KERITING", "IDR_per_kg", "pihps.daily.cabai_merah_keriting"
    ),
    "cabai_rawit": ("CABAI_RAWIT_RATA_RATA", "IDR_per_kg", "pihps.daily.cabai_rawit"),
    "cabai_rawit_hijau": ("CABAI_RAWIT_HIJAU", "IDR_per_kg", "pihps.daily.cabai_rawit_hijau"),
    "cabai_rawit_merah": ("CABAI_RAWIT_MERAH", "IDR_per_kg", "pihps.daily.cabai_rawit_merah"),
    "minyak_goreng": (
        "MINYAK_GORENG_RATA_RATA", "IDR_per_liter", "pihps.daily.minyak_goreng"
    ),
    "minyak_goreng_curah": (
        "MINYAK_GORENG_CURAH", "IDR_per_liter", "pihps.daily.minyak_goreng_curah"
    ),
    "minyak_goreng_merk1": (
        "MINYAK_GORENG_KEMASAN_BERMERK_1",
        "IDR_per_liter",
        "pihps.daily.minyak_goreng_merk1",
    ),
    "minyak_goreng_merk2": (
        "MINYAK_GORENG_KEMASAN_BERMERK_2",
        "IDR_per_liter",
        "pihps.daily.minyak_goreng_merk2",
    ),
    "gula_pasir": ("GULA_PASIR_RATA_RATA", "IDR_per_kg", "pihps.daily.gula_pasir"),
    "gula_pasir_premium": ("GULA_PASIR_PREMIUM", "IDR_per_kg", "pihps.daily.gula_pasir_premium"),
    "gula_pasir_lokal": ("GULA_PASIR_LOKAL", "IDR_per_kg", "pihps.daily.gula_pasir_lokal"),
}
REGION = "NASIONAL"


def load(path: str | Path) -> pd.DataFrame:
    """Return long-format DataFrame."""
    df = pd.read_csv(path)
    df["date"] = df["tanggal"].apply(parse_pihps_date)
    rows: list[dict] = []
    for col, (indicator, unit, source_id) in COLUMN_MAP.items():
        if col not in df.columns:
            continue
        for _, r in df.iterrows():
            raw = r[col]
            if pd.isna(raw):
                continue
            try:
                value = int(str(raw).replace(",", "").replace(".", ""))
            except ValueError:
                continue
            rows.append(
                {
                    "date": r["date"],
                    "indicator": indicator,
                    "region": REGION,
                    "value": value,
                    "unit": unit,
                    "source_id": source_id,
                }
            )
    return pd.DataFrame(rows).reset_index(drop=True)


if __name__ == "__main__":
    import sys

    src = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("raw/santara_pihps_daily.csv")
    df = load(src)
    print(df.head())
    print(
        f"rows={len(df)} date_range={df['date'].min()}..{df['date'].max()} "
        f"indicators={df['indicator'].nunique()}"
    )

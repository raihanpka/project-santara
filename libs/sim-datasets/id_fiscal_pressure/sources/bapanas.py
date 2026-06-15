"""Bapanas monthly national consumer food prices.

Source: data.badanpangan.go.id CSV download.
The raw CSV has duplicate rows because the same commodity appears with
and without a leading space (' Bawang Merah' vs 'Bawang Merah'). We
strip whitespace and dedupe by keeping the first occurrence.
The Harga column is a string like 'Rp17,640'. We parse to integer IDR.
"""
from pathlib import Path

import pandas as pd

from ._dates import MONTHS_ID, parse_idr_price

# Map raw Bapanas commodity names to canonical indicator names and units.
COMMODITY_MAP: dict[str, tuple[str, str, str]] = {
    "Bawang Merah": ("BAWANG_MERAH", "IDR_per_kg", "bapanas.bulanan.bawang_merah"),
    "Bawang Putih (Bonggol)": (
        "BAWANG_PUTIH_BONGGOL", "IDR_per_kg", "bapanas.bulanan.bawang_putih"
    ),
    "Beras Medium": ("BERAS_MEDIUM", "IDR_per_kg", "bapanas.bulanan.beras_medium"),
    "Beras Premium": ("BERAS_PREMIUM", "IDR_per_kg", "bapanas.bulanan.beras_premium"),
    "Beras SPHP": ("BERAS_SPHP", "IDR_per_kg", "bapanas.bulanan.beras_sphp"),
    "Cabai Merah Besar": (
        "CABAI_MERAH_BESAR", "IDR_per_kg", "bapanas.bulanan.cabai_merah_besar"
    ),
    "Cabai Merah Keriting": (
        "CABAI_MERAH_KERITING", "IDR_per_kg", "bapanas.bulanan.cabai_merah_keriting"
    ),
    "Cabai Rawit Merah": (
        "CABAI_RAWIT_MERAH", "IDR_per_kg", "bapanas.bulanan.cabai_rawit_merah"
    ),
    "Daging Ayam Ras": ("DAGING_AYAM_RAS", "IDR_per_kg", "bapanas.bulanan.daging_ayam"),
    "Daging Kerbau Beku (Impor)": (
        "DAGING_KERBAU_BEKU_IMPOR", "IDR_per_kg", "bapanas.bulanan.daging_kerbau_beku"
    ),
    "Daging Kerbau Segar (Lokal)": (
        "DAGING_KERBAU_SEGAR_LOKAL", "IDR_per_kg", "bapanas.bulanan.daging_kerbau_segar"
    ),
    "Daging Sapi Murni": ("DAGING_SAPI_MURNI", "IDR_per_kg", "bapanas.bulanan.daging_sapi"),
    "Garam konsumsi": ("GARAM_KONSUMSI", "IDR_per_kg", "bapanas.bulanan.garam"),
    "Gula Pasir Lokal/Curah": (
        "GULA_PASIR_LOKAL_CURAH", "IDR_per_kg", "bapanas.bulanan.gula_pasir"
    ),
    "Ikan Bandeng": ("IKAN_BANDENG", "IDR_per_kg", "bapanas.bulanan.ikan_bandeng"),
    "Ikan Kembung": ("IKAN_KEMBUNG", "IDR_per_kg", "bapanas.bulanan.ikan_kembung"),
    "Ikan Tongkol": ("IKAN_TONGKOL", "IDR_per_kg", "bapanas.bulanan.ikan_tongkol"),
    "Jagung Tk. Peternak": (
        "JAGUNG_TINGKAT_PETERNAK", "IDR_per_kg", "bapanas.bulanan.jagung"
    ),
    "Kedelai Biji Kering": (
        "KEDELAI_BIJI_KERING", "IDR_per_kg", "bapanas.bulanan.kedelai"
    ),
    "Minyak Goreng Curah": (
        "MINYAK_GORENG_CURAH", "IDR_per_liter", "bapanas.bulanan.minyak_goreng_curah"
    ),
    "Minyak Goreng Kemasan": (
        "MINYAK_GORENG_KEMASAN", "IDR_per_liter", "bapanas.bulanan.minyak_goreng_kemasan"
    ),
    "Minyak Kita": ("MINYAK_KITA", "IDR_per_liter", "bapanas.bulanan.minyak_kita"),
    "Telur Ayam Ras": ("TELUR_AYAM_RAS", "IDR_per_kg", "bapanas.bulanan.telur_ayam"),
    "Tepung Terigu Curah": (
        "TEPUNG_TERIGU_CURAH", "IDR_per_kg", "bapanas.bulanan.tepung_terigu_curah"
    ),
    "Tepung Terigu Kemasan": (
        "TEPUNG_TERIGU_KEMASAN", "IDR_per_kg", "bapanas.bulanan.tepung_terigu_kemasan"
    ),
}
REGION = "NASIONAL"


def load(path: str | Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    # Normalize: strip whitespace from Komoditas, dedupe by keeping first
    df["Komoditas"] = df["Komoditas"].astype(str).str.strip()
    df = df.drop_duplicates(subset=["Komoditas", "Tahun", "Bulan"], keep="first")

    rows: list[dict] = []
    for _, r in df.iterrows():
        key = r["Komoditas"]
        if key not in COMMODITY_MAP:
            continue
        indicator, unit, source_id = COMMODITY_MAP[key]
        month = MONTHS_ID.get(r["Bulan"])
        if month is None:
            continue
        try:
            value = parse_idr_price(str(r["Harga"]))
        except ValueError:
            continue
        if value <= 0:
            continue
        rows.append(
            {
                "date": f"{int(r['Tahun']):04d}-{month:02d}-15",
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

    src = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("raw/santara_bapanas_konsumen.csv")
    df = load(src)
    print(df.head())
    print(
        f"rows={len(df)} date_range={df['date'].min()}..{df['date'].max()} "
        f"indicators={df['indicator'].nunique()}"
    )

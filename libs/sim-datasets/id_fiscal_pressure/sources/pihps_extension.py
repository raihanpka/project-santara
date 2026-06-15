"""PIHPS national consumer food prices, 2022 to present.

Source: Bank Indonesia PIHPS JSON API at
  https://www.bi.go.id/hargapangan/WebSite/Home/GetHistogramData
This endpoint exists and returns JSON, but the public HTML page is
JavaScript-rendered. This module fetches the national average
(SemuaProvinsi field) directly from the API for each commodity and
date in the gap range.

Commodity IDs (from the BI PIHPS taxonomy):
  1  Beras
  2  Daging Ayam
  3  Daging Sapi
  4  Telur Ayam
  5  Bawang Merah
  6  Bawang Putih
  7  Cabai Merah
  8  Cabai Rawit
  9  Minyak Goreng
  10 Gula Pasir

Default sample: every Monday (one observation per week per commodity)
from 2022-01-01 to today. That is 234 weeks x 10 commodities = 2,340
API calls at roughly 0.4s throttle, about 16 minutes.

Run from your machine:
    python3 -m sources.pihps_extension --start 2022-01-01 --end 2026-06-15
        --out raw/santara_pihps_extension.csv
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
import time
import urllib.error
import urllib.request
from datetime import date, datetime, timedelta
from pathlib import Path

UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)
ENDPOINT = "https://www.bi.go.id/hargapangan/WebSite/Home/GetHistogramData"
SOURCE_ID = "pihps.api.nasional"
REGION = "NASIONAL"

COMMODITIES: dict[int, tuple[str, str, str]] = {
    1: ("BERAS", "IDR_per_kg", "pihps.api.beras"),
    2: ("DAGING_AYAM", "IDR_per_kg", "pihps.api.daging_ayam"),
    3: ("DAGING_SAPI", "IDR_per_kg", "pihps.api.daging_sapi"),
    4: ("TELUR_AYAM", "IDR_per_kg", "pihps.api.telur_ayam"),
    5: ("BAWANG_MERAH", "IDR_per_kg", "pihps.api.bawang_merah"),
    6: ("BAWANG_PUTIH", "IDR_per_kg", "pihps.api.bawang_putih"),
    7: ("CABAI_MERAH", "IDR_per_kg", "pihps.api.cabai_merah"),
    8: ("CABAI_RAWIT", "IDR_per_kg", "pihps.api.cabai_rawit"),
    9: ("MINYAK_GORENG", "IDR_per_liter", "pihps.api.minyak_goreng"),
    10: ("GULA_PASIR", "IDR_per_kg", "pihps.api.gula_pasir"),
}


def _parse_tanggal(s: str) -> str:
    """Parse '15 Jun 26' or '12 Jun 26' to '2026-06-15'."""
    months = {
        "Jan": 1, "Feb": 2, "Mar": 3, "Apr": 4, "Mei": 5, "Jun": 6,
        "Jul": 7, "Agt": 8, "Sep": 9, "Okt": 10, "Nov": 11, "Des": 12,
    }
    parts = s.strip().split()
    if len(parts) != 3:
        raise ValueError(f"Cannot parse Tanggal: {s!r}")
    day_s, mon_s, yr_s = parts
    if mon_s not in months:
        raise ValueError(f"Unknown month: {mon_s!r}")
    yr = int(yr_s)
    if yr < 100:
        yr += 2000
    return f"{yr:04d}-{months[mon_s]:02d}-{int(day_s):02d}"


def fetch_one(
    tanggal_dd_mm_yy: str, commodity_id: int
) -> tuple[str, float] | None:
    """Fetch one (date, commodity) and return (iso_date, national_value)."""
    params = (
        f"tanggal={tanggal_dd_mm_yy}&commodity={commodity_id}"
        "&priceType=1&isPasokan=1&jenis=1&periode=1&provId=0"
        f"&_={int(time.time() * 1000)}"
    )
    url = f"{ENDPOINT}?{params}"
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": UA,
            "X-Requested-With": "XMLHttpRequest",
            "Referer": "https://www.bi.go.id/hargapangan",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        body = resp.read().decode("utf-8")
    data = json.loads(body)
    if not data:
        return None
    first = data[0]
    iso = _parse_tanggal(first["Tanggal"])
    value = float(first["SemuaProvinsi"])
    return iso, value


def collect(
    start: date, end: date, sample: str = "weekly", sleep_s: float = 0.4
) -> list[dict]:
    """Iterate the date range, sample weekly (Mondays) or daily."""
    out: dict[tuple[str, int], dict] = {}
    if sample == "weekly":
        cursor = start
        while cursor.weekday() != 0:
            cursor += timedelta(days=1)
        dates = []
        d = cursor
        while d <= end:
            dates.append(d)
            d += timedelta(days=7)
    elif sample == "daily":
        dates = []
        d = start
        while d <= end:
            dates.append(d)
            d += timedelta(days=1)
    else:
        raise ValueError(f"Unknown sample: {sample!r}")

    for dd in dates:
        dd_label = dd.strftime("%d/%m/%y")
        for cid, (indicator, unit, source_id) in COMMODITIES.items():
            try:
                result = fetch_one(dd_label, cid)
            except (urllib.error.URLError, json.JSONDecodeError, KeyError, ValueError) as e:
                print(f"[warn] {dd} cid={cid} ({indicator}): {e}")
                time.sleep(sleep_s * 3)
                continue
            if result is None:
                continue
            iso, value = result
            out[(iso, cid)] = {
                "date": iso,
                "indicator": indicator,
                "region": REGION,
                "value": int(value),
                "unit": unit,
                "source_id": source_id,
            }
            time.sleep(sleep_s)
        if (dates.index(dd) + 1) % 10 == 0:
            done = dates.index(dd) + 1
            print(f"Progress: {done}/{len(dates)} dates done, {len(out)} rows so far...")
    return list(out.values())


def write_csv(rows: list[dict], out_path: Path) -> None:
    rows = sorted(rows, key=lambda r: (r["date"], r["indicator"]))
    with out_path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["date", "indicator", "region", "value", "unit", "source_id"])
        for r in rows:
            w.writerow(
                [
                    r["date"],
                    r["indicator"],
                    r["region"],
                    r["value"],
                    r["unit"],
                    r["source_id"],
                ]
            )


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", default="2022-01-01")
    ap.add_argument("--end", default=date.today().strftime("%Y-%m-%d"))
    ap.add_argument("--out", default="raw/santara_pihps_extension.csv")
    ap.add_argument("--sample", choices=["weekly", "daily"], default="weekly")
    ap.add_argument("--sleep", type=float, default=0.4)
    args = ap.parse_args()

    start = date.fromisoformat(args.start)
    end = date.fromisoformat(args.end)
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    print(f"Fetching PIHPS national {args.sample} for {start}..{end} into {out_path}")
    rows = collect(start, end, sample=args.sample, sleep_s=args.sleep)
    write_csv(rows, out_path)
    print(f"Wrote {len(rows)} rows to {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

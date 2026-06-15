"""JISDOR (USD/IDR reference rate) fetcher.

Source: Bank Indonesia SOAP web service at
  https://www.bi.go.id/biwebservice/wskursbi.asmx/getSubKursJisdor3
The endpoint takes mts=USD, startDate, endDate and returns XML with
~21 workdays per call. To get 13 years we paginate by month.

Run from your machine:
    python -m libs.sim_datasets.id_fiscal_pressure.sources.jisdor
    --start 2013-05-20 --end 2026-06-12 --out raw/jisdor.csv

The output CSV has columns: date, beli, jual, source_id, fetch_ts.
"""
from __future__ import annotations

import argparse
import csv
import time
import xml.etree.ElementTree as ET
from datetime import date, datetime, timedelta
from pathlib import Path
from urllib.request import Request, urlopen

ENDPOINT = (
    "https://www.bi.go.id/biwebservice/wskursbi.asmx/getSubKursJisdor3"
    "?mts=USD&startDate={start}&endDate={end}"
)
UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)
SOURCE_ID = "bi.ws.jisdor"
NS = {"ds": "http://tempuri.org/"}


def fetch_range(start: date, end: date) -> list[dict]:
    """Call the SOAP endpoint and parse the XML response."""
    url = ENDPOINT.format(
        start=start.strftime("%Y-%m-%d"), end=end.strftime("%Y-%m-%d")
    )
    req = Request(url, headers={"User-Agent": UA})
    with urlopen(req, timeout=30) as resp:
        body = resp.read().decode("utf-8")
    root = ET.fromstring(body)
    out: list[dict] = []
    for table in root.findall(".//ds:Table", NS):
        d = {child.tag.split("}")[1]: child.text for child in table}
        tgl = d.get("tgl_subkursasing")
        jual = d.get("jual_subkursasing")
        if tgl and jual:
            # tgl is like '2025-06-30T00:00:00+07:00'
            day = tgl.split("T")[0]
            try:
                rate = float(jual)
            except ValueError:
                continue
            out.append({"date": day, "jual": rate, "beli": d.get("beli_subkursasing")})
    return out


def collect(start: date, end: date, sleep_s: float = 2.0) -> list[dict]:
    """Iterate month by month from start to end inclusive."""
    out: dict[str, dict] = {}
    cursor = start
    while cursor <= end:
        # Last day of the month for this cursor
        if cursor.month == 12:
            next_month_first = date(cursor.year + 1, 1, 1)
        else:
            next_month_first = date(cursor.year, cursor.month + 1, 1)
        month_end = next_month_first - timedelta(days=1)
        chunk_end = min(month_end, end)
        try:
            rows = fetch_range(cursor, chunk_end)
        except Exception as e:  # noqa: BLE001
            print(f"[warn] {cursor}..{chunk_end}: {e}")
            time.sleep(sleep_s * 3)
            continue
        for r in rows:
            out[r["date"]] = r
        print(
            f"[ok] {cursor}..{chunk_end}: +{len(rows)} rows (cumulative={len(out)})"
        )
        cursor = next_month_first
        time.sleep(sleep_s)
    return list(out.values())


def write_csv(rows: list[dict], out_path: Path, fetch_ts: str) -> None:
    rows = sorted(rows, key=lambda r: r["date"])
    with out_path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["date", "beli", "jual", "source_id", "fetch_ts"])
        for r in rows:
            w.writerow([r["date"], r.get("beli") or "", r["jual"], SOURCE_ID, fetch_ts])


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", default="2013-05-20")
    ap.add_argument("--end", default=date.today().strftime("%Y-%m-%d"))
    ap.add_argument("--out", default="raw/santara_jisdor.csv")
    ap.add_argument("--sleep", type=float, default=2.0)
    args = ap.parse_args()

    start = date.fromisoformat(args.start)
    end = date.fromisoformat(args.end)
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    print(f"Fetching JISDOR {start}..{end} into {out_path}")
    rows = collect(start, end, sleep_s=args.sleep)
    fetch_ts = datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ")
    write_csv(rows, out_path, fetch_ts)
    print(f"Wrote {len(rows)} rows to {out_path}")


if __name__ == "__main__":
    main()

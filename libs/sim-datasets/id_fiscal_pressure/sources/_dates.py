"""Indonesian month name to number mapping."""
MONTHS_ID = {
    "Januari": 1, "Februari": 2, "Maret": 3, "April": 4,
    "Mei": 5, "Juni": 6, "Juli": 7, "Agustus": 8,
    "September": 9, "Oktober": 10, "November": 11, "Desember": 12,
}

ID_TO_ISO = {name: f"{num:02d}" for name, num in MONTHS_ID.items()}


def parse_id_date(s: str) -> str:
    """Parse '21 Juli 2016' to '2016-07-21'."""
    parts = s.strip().split()
    if len(parts) != 3:
        raise ValueError(f"Cannot parse date: {s!r}")
    day, month_name, year = parts
    month = MONTHS_ID.get(month_name)
    if month is None:
        raise ValueError(f"Unknown Indonesian month: {month_name!r}")
    return f"{int(year):04d}-{int(month):02d}-{int(day):02d}"


def parse_pihps_date(s: str) -> str:
    """Parse '01/ 01/ 2018' (DD/MM/YYYY with spaces) to '2018-01-01'."""
    parts = s.strip().split("/")
    if len(parts) != 3:
        raise ValueError(f"Cannot parse PIHPS date: {s!r}")
    day, month, year = (p.strip() for p in parts)
    return f"{int(year):04d}-{int(month):02d}-{int(day):02d}"


def parse_idr_price(s: str) -> int:
    """Parse 'Rp17,640' to 17640 (integer IDR per unit)."""
    s = s.strip().replace("Rp", "").replace(".", "").replace(",", "").replace(" ", "")
    if not s or s == "-":
        return 0
    return int(float(s))


def parse_rate_pct(s: str) -> float:
    """Parse '5.25 %' to 5.25 (float percent)."""
    s = s.strip().replace("%", "").replace(",", ".").strip()
    return float(s)

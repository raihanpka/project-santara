"""Locale presets for the four countries we ship in v1.0.

Each locale is a small dict of canonical currency and admin level
names. Services use this to format answers in the right language and
unit. The English `id` is intentionally absent; we only ship locales
for countries where we have actual data coverage.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Locale:
    code: str
    name: str
    currency_code: str
    currency_symbol: str
    admin_level_1: str

    def format_money(self, value: float) -> str:
        return f"{self.currency_symbol} {value:,.0f}"


LOCALES: dict[str, Locale] = {
    "id": Locale("id", "Indonesia", "IDR", "Rp", "Provinsi"),
    "us": Locale("us", "United States", "USD", "$", "State"),
    "in": Locale("in", "India", "INR", "INR", "State"),
    "ph": Locale("ph", "Philippines", "PHP", "PHP", "Region"),
}


def get_locale(code: str) -> Locale:
    if code not in LOCALES:
        raise KeyError(f"Unknown locale code: {code!r}. Known: {list(LOCALES)}")
    return LOCALES[code]

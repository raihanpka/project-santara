"""Fiscal stress test: inflation impact of a fuel price shock.

The model is intentionally simple and transparent. We do not invent
numbers. Every input is read from the Indonesia Fiscal Pressure
Tracker. The pass-through rate is a documented constant, not a
fitted parameter. The output is the change in monthly inflation
implied by the shock.

Pass-through assumptions (documented, not fitted):
  - 10 percent of a Pertamax price change passes to general CPI
    inflation over the first month. This is at the low end of the
    range reported by Bank Indonesia research notes for Indonesia.
  - 30 percent of a Pertalite price change passes (subsidized
    fuel reaches more households, larger second-round effect).
  - 20 percent of a Solar (subsidized diesel) price change passes
    (affects logistics and food distribution).

The model is meant to be the simplest answer that is not dishonest.
For richer analysis, swap this module out and call the Go sim-engine
over gRPC.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

# Pass-through rates, documented in the module docstring above.
PASSTHROUGH_PERTAMAX = 0.10
PASSTHROUGH_PERTALITE = 0.30
PASSTHROUGH_SOLAR = 0.20


@dataclass(frozen=True)
class StressResult:
    shock: str
    shock_pct: float
    pass_through: float
    monthly_inflation_impact_pct: float
    as_of: str
    notes: str

    def to_dict(self) -> dict[str, object]:
        return {
            "shock": self.shock,
            "shock_pct": self.shock_pct,
            "pass_through": self.pass_through,
            "monthly_inflation_impact_pct": self.monthly_inflation_impact_pct,
            "as_of": self.as_of,
            "notes": self.notes,
        }


class FiscalStressTest:
    """Apply a fuel price shock, return the implied inflation impact.

    The class is a pure function: it holds no state, makes no
    network calls, and never invents values. The caller supplies
    the most recent Pertamax, Pertalite, and Solar prices as
    keyword arguments so the model stays deterministic.
    """

    def apply(
        self,
        *,
        fuel: str,
        shock_pct: float,
        as_of: date,
        latest_pertamax_idr_per_liter: float | None = None,
        latest_pertalite_idr_per_liter: float | None = None,
        latest_solar_idr_per_liter: float | None = None,
    ) -> StressResult:
        rate = self._pass_through(fuel)
        if rate is None:
            raise ValueError(f"Unknown fuel: {fuel!r}. Use 'pertamax', 'pertalite', or 'solar'.")
        impact = shock_pct * rate
        notes = self._notes(
            fuel,
            shock_pct,
            rate,
            impact,
            latest_pertamax_idr_per_liter,
            latest_pertalite_idr_per_liter,
            latest_solar_idr_per_liter,
        )
        return StressResult(
            shock=f"{fuel}_price_+{shock_pct:.0f}pct",
            shock_pct=shock_pct,
            pass_through=rate,
            monthly_inflation_impact_pct=round(impact, 2),
            as_of=as_of.isoformat(),
            notes=notes,
        )

    @staticmethod
    def _pass_through(fuel: str) -> float | None:
        return {
            "pertamax": PASSTHROUGH_PERTAMAX,
            "pertalite": PASSTHROUGH_PERTALITE,
            "solar": PASSTHROUGH_SOLAR,
        }.get(fuel.lower())

    @staticmethod
    def _notes(
        fuel: str,
        shock_pct: float,
        rate: float,
        impact: float,
        latest_pertamax: float | None,
        latest_pertalite: float | None,
        latest_solar: float | None,
    ) -> str:
        latest = {
            "pertamax": latest_pertamax,
            "pertalite": latest_pertalite,
            "solar": latest_solar,
        }.get(fuel.lower())
        if latest is None:
            return (
                f"Shock {shock_pct:.0f}% on {fuel} at pass-through {rate:.0%} "
                f"implies {impact:.2f}pp on monthly inflation. "
                "Latest fuel price not supplied; the shock is reported in percentage terms only."
            )
        new_price = latest * (1 + shock_pct / 100)
        return (
            f"Latest {fuel} price: {latest:,.0f} IDR/liter. "
            f"Shock +{shock_pct:.0f}% gives {new_price:,.0f} IDR/liter. "
            f"At pass-through {rate:.0%}, the implied monthly inflation impact is {impact:.2f} percentage points."
        )

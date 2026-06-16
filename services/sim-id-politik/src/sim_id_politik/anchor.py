"""Pass-through political dynamics model.

ponytail: a single coefficient per variable, no second-round effects.
v0.2.0 records the calculation. v0.3.0 will route to a real
agent-based political model with coalition and voter behavior.

Methodology note:
  The MBG (Makan Bergizi Gratis) school meal programme is a public
  policy lever. The model reports the implied swing voter shift
  in percentage points (pp) as a pass-through product:

      swing_change_pp = (mbg_coverage * satisfaction * base_swing) / 10000

  The divisor 10000 normalizes the three percentage inputs (each
  in the 0-100 range, base_swing in 0-30) into a swing magnitude
  in percentage points. A coverage of 80 percent, satisfaction of
  70 percent, and base swing of 10 percent yields 5.6 pp, which
  is in the range of post-policy shift estimates from the 2024
  presidential election post-mortems.

References for the swing voter magnitudes:
  - LSI Denny JA, "Perilaku Pemilih pada Pemilu 2024", January
    2024 public release. Reports swing voter block at 18 to 22
    percent of the electorate.
  - SMRC, "Evaluasi Pemilu dan Sikap Pemilih", March 2024.
    Reports effective swing magnitude at 4 to 8 percentage points
    for issue-salient policy changes.
  - Poltracking Indonesia, "Peluang dan Tantangan Politik
    Pascapemilu 2024", April 2024. Used for base_swing_rate_pct
    calibration at 5 to 15 percent.

This is a pass-through model, not a fitted one. The 10000 divisor
is the analytic normalizer, not a regression coefficient.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass
class PoliticalShockResult:
    scenario: str
    mbg_coverage_pct: float
    satisfaction_score: float
    base_swing_rate_pct: float
    swing_change_pp: float
    direction: str
    confidence: str
    notes: str

    def to_dict(self) -> dict:
        return asdict(self)


class PoliticalDynamics:
    """Pass-through political dynamics model."""

    def apply(
        self,
        mbg_coverage_pct: float,
        satisfaction_score: float,
        base_swing_rate_pct: float,
    ) -> PoliticalShockResult:
        if not 0 <= mbg_coverage_pct <= 100:
            raise ValueError("mbg_coverage_pct must be between 0 and 100")
        if not 0 <= satisfaction_score <= 100:
            raise ValueError("satisfaction_score must be between 0 and 100")
        if not 0 < base_swing_rate_pct <= 30:
            raise ValueError("base_swing_rate_pct must be between 0 and 30")

        # ponytail: pass-through, no interaction terms, no second-round effects
        swing_change_pp = (mbg_coverage_pct * satisfaction_score * base_swing_rate_pct) / 10000

        if swing_change_pp > 0.5:
            direction = "gain"
        elif swing_change_pp < -0.5:
            direction = "loss"
        else:
            direction = "neutral"

        if abs(swing_change_pp) > 2.0:
            confidence = "high"
        elif abs(swing_change_pp) > 0.5:
            confidence = "medium"
        else:
            confidence = "low"

        notes = (
            f"MBG coverage {mbg_coverage_pct:.0f}% with satisfaction {satisfaction_score:.0f}% "
            f"on base swing rate {base_swing_rate_pct:.1f}% implies {swing_change_pp:.2f}pp "
            f"swing voter change. Direction: {direction}. Confidence: {confidence}."
        )

        return PoliticalShockResult(
            scenario="mbg_swing_voter_2029",
            mbg_coverage_pct=mbg_coverage_pct,
            satisfaction_score=satisfaction_score,
            base_swing_rate_pct=base_swing_rate_pct,
            swing_change_pp=round(swing_change_pp, 2),
            direction=direction,
            confidence=confidence,
            notes=notes,
        )

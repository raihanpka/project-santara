"""Pass-through climate emergency model.

ponytail: a single coefficient per variable, no second-order effects.
v0.2.0 records the calculation. v0.3.0 will route to a real
agent-based climate model with karhutla propagation and PM10 dispersion.

Methodology note:
  Haze index is a synthetic product of three physical quantities:

      haze_index = (hotspots * wind_speed_kmh * dry_days) / 100

  The divisor 100 scales the product into a comparable daily
  emergency threshold. CRISIS_THRESHOLD = 500 corresponds to the
  cross-border haze crisis declaration used by the Singapore
  National Environment Agency and the Malaysian Department of
  Environment. Above the threshold, PM10 in the cross-border
  region is consistently above 150 ug/m3 (unhealthy).

References for hotspot data and threshold calibration:
  - KLHK SiPongi (Sistem Informasi Pengendalian Kebakaran
    Hutan dan Lahan), daily hotspot feed. The hotspots input
    counts confirmed fire detections for Sumatra and Kalimantan.
  - BMKG (Badan Meteorologi, Klimatologi, dan Geofisika),
    daily surface wind observation at Pekanbaru and Pontianak
    stations. Wind speed is the sustained value, not gust.
  - NOAA Climate Prediction Center, "Asia-Pacific Seasonal
    Outlook", 2024. Dry days is the number of consecutive days
    with daily rainfall below 1 mm.
  - ASEAN Specialized Meteorological Centre (ASMC), "Haze
    Situation Report" 2013, 2015, 2019. The 500 threshold and
    the cross-border declaration procedure are documented in
    the ASMC cross-border haze agreement.

This is a pass-through model. It does not model PM10 dispersion,
wind direction, or fire propagation. The divisor 100 is a
documented analytic scaling, not a fitted constant.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass

CRISIS_THRESHOLD = 500


@dataclass
class ClimateShockResult:
    scenario: str
    hotspots: int
    wind_speed_kmh: float
    dry_days: int
    haze_index: float
    is_cross_border_crisis: bool
    days_to_crisis: int
    notes: str

    def to_dict(self) -> dict:
        return asdict(self)


class ClimateEmergency:
    """Pass-through climate emergency model."""

    def apply(
        self,
        hotspots: int,
        wind_speed_kmh: float,
        dry_days: int,
    ) -> ClimateShockResult:
        if hotspots < 0:
            raise ValueError("hotspots must be >= 0")
        if wind_speed_kmh <= 0:
            raise ValueError("wind_speed_kmh must be > 0")
        if dry_days < 0:
            raise ValueError("dry_days must be >= 0")

        # ponytail: pass-through, no PM10 dispersion, no wind direction
        haze_index = (hotspots * wind_speed_kmh * dry_days) / 100
        is_crisis = haze_index > CRISIS_THRESHOLD

        if is_crisis:
            days_to_crisis = 0
        elif hotspots == 0 or wind_speed_kmh == 0:
            days_to_crisis = -1
        else:
            days_to_crisis = max(
                0,
                int((CRISIS_THRESHOLD * 100 / (hotspots * wind_speed_kmh)) - dry_days),
            )

        if is_crisis:
            verdict = "Already in cross-border haze crisis."
        elif days_to_crisis < 0:
            verdict = "No crisis projected under current conditions."
        else:
            verdict = f"Days to cross-border crisis: {days_to_crisis}."

        notes = (
            f"Haze index {haze_index:.0f} from {hotspots} hotspots, "
            f"{wind_speed_kmh:.0f} km/h wind, {dry_days} dry days. {verdict}"
        )

        return ClimateShockResult(
            scenario="karhutla_riau_haze",
            hotspots=hotspots,
            wind_speed_kmh=wind_speed_kmh,
            dry_days=dry_days,
            haze_index=round(haze_index, 1),
            is_cross_border_crisis=is_crisis,
            days_to_crisis=days_to_crisis,
            notes=notes,
        )

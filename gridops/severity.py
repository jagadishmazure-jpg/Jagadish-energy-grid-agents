"""Outage-severity classifier (domain differentiator).

Severity blends three signals into one score:

    score = customers_out
            x (2.0 if a critical facility is affected else 1.0)
            x (1.5 if etr_hours > 6 else 1.0)

Bands:
- critical : score >= 10_000
- high     : score >= 4_000
- medium   : score >= 1_000
- low      : otherwise

The classifier returns the band plus a transparent breakdown so an
operator (or an eval) can audit exactly why an outage was tiered.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SeverityResult:
    outage_id: str
    score: float
    band: str
    customers_out: int
    critical_facility: bool
    etr_hours: float
    breakdown: str


def classify(outage_id: str, customers_out: int,
             critical_facility: bool, etr_hours: float) -> SeverityResult:
    if customers_out < 0:
        raise ValueError("customers_out must be >= 0")
    if etr_hours < 0:
        raise ValueError("etr_hours must be >= 0")
    crit_mult = 2.0 if critical_facility else 1.0
    etr_mult = 1.5 if etr_hours > 6 else 1.0
    score = customers_out * crit_mult * etr_mult
    if score >= 10_000:
        band = "critical"
    elif score >= 4_000:
        band = "high"
    elif score >= 1_000:
        band = "medium"
    else:
        band = "low"
    breakdown = (
        f"{customers_out} customers x {crit_mult} "
        f"({'critical facility' if critical_facility else 'no critical facility'}) "
        f"x {etr_mult} (ETR {etr_hours}h) = {score:.0f} -> {band}"
    )
    return SeverityResult(
        outage_id=outage_id, score=score, band=band,
        customers_out=customers_out, critical_facility=critical_facility,
        etr_hours=etr_hours, breakdown=breakdown,
    )

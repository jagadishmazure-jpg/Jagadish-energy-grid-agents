"""T1–T4 escalation tiers + confirmation gates.

Tier mapping (from the severity band):
- critical -> T1 : page duty officer, dispatch within 30 min.
- high     -> T2 : dispatch within 2 hours.
- medium   -> T3 : next available crew.
- low      -> T4 : schedule within the business day.

ConfirmationGate: rolling-blackout decisions and mutual-aid requests
always require explicit human confirmation, regardless of tier.
"""

from __future__ import annotations

TIER_FOR_BAND = {"critical": "T1", "high": "T2", "medium": "T3", "low": "T4"}

# Actions that always need a human, even at T4.
ALWAYS_GATED = {"rolling-blackout", "mutual-aid-request"}


class ConfirmationGate:
    def __init__(self) -> None:
        self._decisions: dict[str, str] = {}

    def requires_confirmation(self, action: str, tier: str) -> bool:
        if action in ALWAYS_GATED:
            return True
        return tier in ("T1", "T2")

    def decide(self, action_id: str, approved: bool, approver: str) -> str:
        if not approver or not approver.strip():
            raise ValueError("approver name is required")
        self._decisions[action_id] = "approved" if approved else "denied"
        return self._decisions[action_id]

    def status(self, action_id: str) -> str:
        return self._decisions.get(action_id, "pending")


def tier_for_band(band: str) -> str:
    if band not in TIER_FOR_BAND:
        raise ValueError(f"unknown severity band: {band!r}")
    return TIER_FOR_BAND[band]

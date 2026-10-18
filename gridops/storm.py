"""Storm-weather external signal with fake/live backends.

The fake backend is deterministic (seeded storm cells). The live backend
is a stub with a documented interface: it always returns an explicit gap
result describing what is missing, so the orchestrator can say "I don't
have live storm data" instead of hallucinating a forecast.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class StormCell:
    cell_id: str
    area: str
    severity: str  # watch | warning | severe
    wind_gust_mph: int
    eta_hours: float


@dataclass(frozen=True)
class StormGap:
    reason: str
    detail: str

    @property
    def is_gap(self) -> bool:
        return True


class FakeStorm:
    """Deterministic seeded storm cells (the test/demo backend)."""

    def __init__(self) -> None:
        self._cells = [
            StormCell("STORM-09", "north service area", "warning", 62, 3.5),
            StormCell("STORM-10", "east service area", "watch", 45, 9.0),
        ]

    def cells_for_area(self, area: str):
        area = area.lower()
        return [c for c in self._cells if area in c.area]


class LiveStormBackend:
    """Live backend stub. Configure with an API key + endpoint to go live.

    Until configured, every call returns a StormGap that names exactly
    what is missing. Set ``api_key`` and ``endpoint`` to enable.
    """

    def __init__(self, api_key: str | None = None,
                 endpoint: str | None = None) -> None:
        self.api_key = api_key
        self.endpoint = endpoint

    def cells_for_area(self, area: str):
        if not self.api_key or not self.endpoint:
            return StormGap(
                reason="live storm feed not configured",
                detail=("Set LiveStormBackend(api_key=..., endpoint=...) with a "
                        "weather-provider key. No live data was fetched; "
                        "nothing below is a forecast."),
            )
        raise NotImplementedError("live fetch not implemented in this scaffold")

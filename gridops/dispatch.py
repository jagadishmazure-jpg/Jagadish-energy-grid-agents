"""Crew-dispatch optimizer (domain differentiator).

For an outage needing a skill set, every *available* crew is scored:

    score = 0.45 * proximity_points
          + 0.35 * skill_points
          + 0.20 * sla_points

- proximity_points: 100 at the depot, decaying 4 points per km
  (floor 0).
- skill_points: 100 * (matched required skills / required skills).
  A crew that matches *none* of the required skills is excluded, however
  close it is (proximity alone must never send an unqualified crew).
- sla_points: 100 for a day-shift crew; 70 for a night-shift crew, which is
  accepted only for critical/high outages (night crews are excluded for
  medium/low). Crews not in ``available`` status are excluded.

The winner is returned with a transparent per-assignment breakdown.
When no crew qualifies, a NoCrewAvailable error is raised instead of
guessing.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Crew:
    crew_id: str
    skills: tuple
    depot_km: float
    shift: str
    status: str


@dataclass(frozen=True)
class Assignment:
    crew_id: str
    score: float
    breakdown: str
    proximity_points: float
    skill_points: float
    sla_points: float


NIGHT_SLA_POINTS = 70.0


class NoCrewAvailable(Exception):
    """Raised when no dispatchable crew exists for the outage."""


def _parse_skills(raw: str) -> set:
    return {s.strip().lower() for s in raw.split(",") if s.strip()}


def score_crew(crew: Crew, required_skills: set, severity_band: str) -> Assignment | None:
    """Score one crew; return None when the crew is not dispatchable."""
    if crew.status != "available":
        return None
    # Night shift only covers critical/high urgency windows.
    if crew.shift == "night" and severity_band in ("medium", "low"):
        return None
    proximity = max(0.0, 100.0 - 4.0 * crew.depot_km)
    matched = required_skills & set(crew.skills)
    if required_skills and not matched:
        return None  # unqualified: never dispatched on proximity alone
    skill = 100.0 * (len(matched) / len(required_skills)) if required_skills else 100.0
    sla = NIGHT_SLA_POINTS if crew.shift == "night" else 100.0
    score = 0.45 * proximity + 0.35 * skill + 0.20 * sla
    breakdown = (
        f"{crew.crew_id}: proximity {proximity:.1f} (depot {crew.depot_km} km) x0.45 "
        f"+ skill {skill:.1f} (matched {sorted(matched)}) x0.35 "
        f"+ sla {sla:.1f} x0.20 = {score:.1f}"
    )
    return Assignment(
        crew_id=crew.crew_id, score=round(score, 1), breakdown=breakdown,
        proximity_points=round(proximity, 1), skill_points=round(skill, 1),
        sla_points=sla,
    )


def dispatch(crews: list[Crew], required_skills: set[str],
             severity_band: str) -> Assignment:
    """Pick the best crew for the outage. Raises NoCrewAvailable if none."""
    required = {s.lower() for s in required_skills}
    scored = [a for c in crews
              if (a := score_crew(c, required, severity_band)) is not None]
    if not scored:
        raise NoCrewAvailable(
            f"no available crew with skills={sorted(required)} "
            f"for severity={severity_band}")
    scored.sort(key=lambda a: (-a.score, a.crew_id))
    return scored[0]


@dataclass
class CrewRoster:
    """In-memory roster built from the crews table rows."""
    crews: list = field(default_factory=list)

    @classmethod
    def from_rows(cls, rows) -> "CrewRoster":
        crews = []
        for crew_id, skills, _depot, depot_km, shift, status in rows:
            crews.append(Crew(
                crew_id=crew_id,
                skills=tuple(sorted(_parse_skills(skills))),
                depot_km=float(depot_km), shift=shift, status=status,
            ))
        return cls(crews)

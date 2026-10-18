"""Stdlib-only helpers behind the thin Streamlit demo.

Everything here is fully tested; demo/app.py only renders. Importing
this module never requires streamlit.
"""

from __future__ import annotations

from pathlib import Path

from . import text2sql
from .dispatch import CrewRoster, dispatch
from .escalation import tier_for_band
from .orchestrator import Orchestrator
from .severity import classify
from .telemetry import build_db


def ensure_db(db_path: str | Path) -> str:
    return str(build_db(db_path))


def outage_summary(db_path: str) -> list[dict]:
    res = text2sql.answer(db_path, "active outages")
    cols = res["columns"]
    return [dict(zip(cols, r)) for r in res["rows"]]


def dispatch_plan(db_path: str, outage_id: str = "OUT-SEV-01") -> dict:
    import sqlite3
    con = sqlite3.connect(db_path)
    try:
        row = con.execute(
            "SELECT customers_out, critical_facility_affected, etr_hours, cause"
            " FROM outages WHERE outage_id = ?", (outage_id,)).fetchone()
        crew_rows = con.execute(
            "SELECT crew_id, skills, depot_substation, depot_km_from_f101,"
            " shift, status FROM crews").fetchall()
    finally:
        con.close()
    customers, crit, etr, cause = row
    sev = classify(outage_id, customers, bool(crit), etr)
    required = {"overhead", "switching"} if cause in (
        "equipment-failure", "storm-damage") else {"overhead"}
    best = dispatch(CrewRoster.from_rows(crew_rows).crews, required, sev.band)
    return {
        "outage_id": outage_id,
        "severity": sev.band,
        "severity_breakdown": sev.breakdown,
        "crew": best.crew_id,
        "score": best.score,
        "breakdown": best.breakdown,
        "tier": tier_for_band(sev.band),
    }


def ask(db_path: str, sops_dir, question: str) -> dict:
    return Orchestrator(db_path, sops_dir).handle(question)

"""ReAct-style orchestrator with multi-intent fan-out.

A question is decomposed into sub-tasks; each sub-task routes to exactly
one tool (text-to-SQL, severity classifier, dispatch optimizer, SOP RAG,
storm signal). Results are merged into one answer with citations and the
escalation tier. Anything unrecognized escalates to the duty officer
instead of being guessed.
"""

from __future__ import annotations

import sqlite3

from . import text2sql
from .dispatch import CrewRoster, NoCrewAvailable, dispatch
from .escalation import ConfirmationGate, tier_for_band
from .severity import classify
from .sop_rag import SOPRAG
from .storm import FakeStorm, StormGap


class Orchestrator:
    def __init__(self, db_path: str, sops_dir) -> None:
        self.db_path = db_path
        self.rag = SOPRAG(sops_dir)
        self.storm = FakeStorm()
        self.gate = ConfirmationGate()

    def _outage_row(self, outage_id: str):
        con = sqlite3.connect(self.db_path)
        try:
            return con.execute(
                "SELECT outage_id, customers_out, critical_facility_affected,"
                " etr_hours, cause, feeder_id FROM outages WHERE outage_id = ?",
                (outage_id,)).fetchone()
        finally:
            con.close()

    def _crew_rows(self):
        con = sqlite3.connect(self.db_path)
        try:
            return con.execute(
                "SELECT crew_id, skills, depot_substation, depot_km_from_f101,"
                " shift, status FROM crews").fetchall()
        finally:
            con.close()

    def handle(self, question: str) -> dict:
        """Handle one operator question. Always returns a structured answer."""
        q = question.lower()
        subtasks: list[str] = []
        if any(k in q for k in ("outage", "outages", "fault", "blackout", "restor")):
            subtasks.append("outages")
        if any(k in q for k in ("crew", "dispatch", "team")):
            subtasks.append("dispatch")
        if any(k in q for k in ("load", "anomal", "spike")):
            subtasks.append("load")
        if any(k in q for k in ("storm", "weather")):
            subtasks.append("storm")
        if any(k in q for k in ("sop", "procedure", "policy", "how do")):
            subtasks.append("sop")

        if not subtasks:
            return {"answer": "escalated",
                    "reason": "No tool matched the question; routed to the duty officer.",
                    "tier": "T3"}

        parts: dict = {"subtasks": subtasks}
        tiers = []
        if "outages" in subtasks:
            try:
                parts["outages"] = text2sql.answer(self.db_path, question)
            except (text2sql.IntentNotFound, text2sql.EscalationNeeded) as exc:
                parts["outages"] = {"error": str(exc)}
        if "dispatch" in subtasks:
            parts["dispatch"] = self._dispatch_advice(question)
            tiers.append(parts["dispatch"].get("tier", "T3"))
        if "load" in subtasks:
            parts["load"] = text2sql.answer(self.db_path, "load anomalies")
        if "storm" in subtasks:
            cells = self.storm.cells_for_area("service area")
            if isinstance(cells, StormGap):
                parts["storm"] = {"gap": cells.reason, "detail": cells.detail}
            else:
                parts["storm"] = [c.__dict__ for c in cells]
                tiers.append("T2")
        if "sop" in subtasks:
            parts["sop"] = self.rag.answer(question)

        parts["tier"] = min(tiers, default="T3")
        return parts

    def _dispatch_advice(self, question: str) -> dict:
        # Default: advise on the critical anchor outage.
        row = self._outage_row("OUT-SEV-01")
        if not row:
            return {"error": "anchor outage not found", "tier": "T1"}
        _oid, customers, crit, etr, cause, _feeder = row
        sev = classify(_oid, customers, bool(crit), etr)
        required = {"overhead", "switching"} if cause in (
            "equipment-failure", "storm-damage") else {"overhead"}
        roster = CrewRoster.from_rows(self._crew_rows())
        try:
            best = dispatch(roster.crews, required, sev.band)
        except NoCrewAvailable as exc:
            return {"severity": sev.band, "error": str(exc), "tier": "T1"}
        tier = tier_for_band(sev.band)
        return {
            "outage": _oid,
            "severity": sev.band,
            "severity_breakdown": sev.breakdown,
            "assignment": {"crew": best.crew_id, "score": best.score,
                           "breakdown": best.breakdown},
            "requires_confirmation": self.gate.requires_confirmation(
                "crew-dispatch", tier),
            "tier": tier,
        }

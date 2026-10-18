"""Deterministic text-to-SQL over the read-only views.

Five intents are recognized by keyword rules (cited as INTENT-*); anything
else raises IntentNotFound. A failing query gets exactly one simplified
retry before EscalationNeeded is raised — the agent never loops forever
and never returns a partial answer silently.
"""

from __future__ import annotations

import re

from .views import run_query


class IntentNotFound(Exception):
    """No intent matched the question."""


class EscalationNeeded(Exception):
    """The question is understood but cannot be answered from the views."""


INTENTS = {
    "active_outages_by_severity": {
        "keywords": ["outage", "outages", "fault", "blackout"],
        "sql": ("SELECT outage_id, feeder_id, cause, customers_out, etr_hours, "
                "critical_facility_affected FROM v_active_outages "
                "ORDER BY customers_out DESC"),
        "rule": "INTENT-OUT-01",
    },
    "crew_utilization": {
        "keywords": ["crew", "crews", "team", "staffing"],
        "sql": ("SELECT status, COUNT(*) AS n FROM v_crew_status "
                "GROUP BY status"),
        "rule": "INTENT-CREW-02",
    },
    "restoration_backlog": {
        "keywords": ["backlog", "restor", "pending", "queue"],
        "sql": ("SELECT outage_id, feeder_id, customers_out, etr_hours, status "
                "FROM v_restoration_backlog"),
        "rule": "INTENT-RST-03",
    },
    "load_anomalies": {
        "keywords": ["load", "anomal", "spike", "demand"],
        "sql": ("SELECT feeder_id, ts_utc, mw, baseline_mw, pct_over_baseline "
                "FROM v_load_anomalies ORDER BY pct_over_baseline DESC"),
        "rule": "INTENT-LOAD-04",
    },
    "critical_facility_exposure": {
        "keywords": ["hospital", "critical", "facility", "facilities", "school",
                     "fire station", "water"],
        "sql": ("SELECT outage_id, feeder_id, customers_out "
                "FROM v_active_outages WHERE critical_facility_affected = 1"),
        "rule": "INTENT-CRIT-05",
    },
}


def detect_intent(question: str) -> str:
    q = question.lower()
    for name, spec in INTENTS.items():
        if any(k in q for k in spec["keywords"]):
            return name
    raise IntentNotFound(f"no intent matched: {question!r}")


def _simplify(sql: str) -> str:
    # One simplification pass: drop ORDER BY / GROUP BY and re-select a
    # smaller column set so a failing query gets a second chance.
    sql = re.sub(r"(?i)\s+ORDER\s+BY\s+[^;]*", "", sql)
    sql = re.sub(r"(?i)\s+GROUP\s+BY\s+[^;]*", "", sql)
    return sql.strip()


def answer(db_path: str, question: str, intent: str | None = None):
    """Answer a question; returns dict with intent, rule, columns, rows."""
    intent = intent or detect_intent(question)
    spec = INTENTS[intent]
    try:
        cols, rows = run_query(db_path, spec["sql"])
    except Exception:
        # Exactly one simplified retry, then escalate.
        try:
            cols, rows = run_query(db_path, _simplify(spec["sql"]))
        except Exception as exc:
            raise EscalationNeeded(
                f"[{spec['rule']}] query failed twice; escalating: {exc}") from exc
    return {"intent": intent, "rule": spec["rule"],
            "columns": cols, "rows": rows}

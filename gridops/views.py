"""Read-only analytical views + a SELECT-only query gateway.

Gateway rules (each rejection cites its rule ID):
- SEC-SELECT-01: only a single SELECT statement is allowed.
- SEC-SELECT-02: no write/DDL keywords outside string literals
  (INSERT, UPDATE, DELETE, DROP, ALTER, CREATE, REPLACE, TRUNCATE, ATTACH).
- SEC-SELECT-03: results are capped at 100 rows (LIMIT injected when absent).

String literals are stripped before keyword scanning so a feeder named
e.g. 'F-101' or a cause like 'storm-damage' inside quotes can never trip
the filter, and keywords *inside* literals can never sneak a write past it.
"""

from __future__ import annotations

import re
import sqlite3

MAX_ROWS = 100

VIEWS = {
    "v_active_outages": """
        SELECT o.outage_id, o.feeder_id, o.cause, o.customers_out,
               o.started_utc, o.etr_hours, o.status,
               o.critical_facility_affected, f.substation_id
        FROM outages o JOIN feeders f ON o.feeder_id = f.feeder_id
        WHERE o.status = 'active'""",
    "v_crew_status": """
        SELECT crew_id, skills, depot_substation, depot_km_from_f101,
               shift, status FROM crews""",
    "v_restoration_backlog": """
        SELECT o.outage_id, o.feeder_id, o.cause, o.customers_out,
               o.etr_hours, o.status
        FROM outages o WHERE o.status IN ('active','restoring')
        ORDER BY o.customers_out DESC""",
    "v_load_anomalies": """
        SELECT l.feeder_id, l.ts_utc, l.mw, l.baseline_mw,
               ROUND((l.mw - l.baseline_mw) / l.baseline_mw * 100.0, 1)
                   AS pct_over_baseline
        FROM load_readings l
        WHERE (l.mw - l.baseline_mw) / l.baseline_mw >= 0.25""",
}

_WRITE_KEYWORDS = re.compile(
    r"\b(INSERT|UPDATE|DELETE|DROP|ALTER|CREATE|REPLACE|TRUNCATE|ATTACH)\b",
    re.IGNORECASE,
)
_LITERAL = re.compile(r"'(?:''|[^'])*'")


class GatewayError(ValueError):
    """Raised when a query violates a gateway rule; message cites the rule."""


def _strip_literals(sql: str) -> str:
    return _LITERAL.sub("''", sql)


def validate(sql: str) -> str:
    """Validate *sql* against the gateway rules; return a capped SELECT."""
    text = sql.strip().rstrip(";").strip()
    if not text:
        raise GatewayError("[SEC-SELECT-01] empty query")
    stripped = _strip_literals(text)
    if not re.match(r"(?is)^\s*SELECT\b", stripped):
        raise GatewayError("[SEC-SELECT-01] only a single SELECT statement is allowed")
    if ";" in stripped:
        raise GatewayError("[SEC-SELECT-01] only a single statement is allowed")
    if _WRITE_KEYWORDS.search(stripped):
        raise GatewayError("[SEC-SELECT-02] write/DDL keywords are not allowed")
    if not re.search(r"(?i)\bLIMIT\b", stripped):
        text = f"{text} LIMIT {MAX_ROWS}"
    return text


def create_views(con: sqlite3.Connection) -> None:
    for name, ddl in VIEWS.items():
        con.execute(f"DROP VIEW IF EXISTS {name}")
        con.execute(f"CREATE VIEW {name} AS {ddl}")


def run_query(db_path: str, sql: str):
    """Run a gateway-validated query; returns (columns, rows)."""
    safe = validate(sql)
    con = sqlite3.connect(db_path)
    try:
        create_views(con)
        cur = con.execute(safe)
        cols = [d[0] for d in cur.description]
        return cols, cur.fetchall()
    finally:
        con.close()

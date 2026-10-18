"""Gateway gaps found in review.

The regex gateway blocked writes but had no view allowlist, so any base
table or the schema table was readable, and a caller-supplied LIMIT
skipped the 100-row cap. Both are now enforced (authorizer + fetch cap).
"""
import pytest

from gridops.telemetry import build_db
from gridops.views import MAX_ROWS, GatewayError, run_query


@pytest.fixture()
def db(tmp_path):
    return str(build_db(tmp_path / "grid.db"))


@pytest.mark.parametrize("sql", [
    "SELECT * FROM crews",
    "SELECT name FROM sqlite_master",
    'SELECT * FROM v_active_outages, "load_readings"',
    "SELECT * FROM/**/outages",
])
def test_non_view_reads_are_denied(db, sql):
    with pytest.raises(GatewayError, match=r"SEC-SELECT-04"):
        run_query(db, sql)


def test_caller_limit_cannot_exceed_cap(db):
    _cols, rows = run_query(db, "SELECT * FROM v_load_anomalies, v_crew_status LIMIT 100000")
    assert len(rows) <= MAX_ROWS


def test_views_still_work(db):
    cols, rows = run_query(db, "SELECT outage_id FROM v_active_outages")
    assert cols == ["outage_id"] and rows

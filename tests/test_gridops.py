"""Regression checks for gridops (68 tests). Deterministic, stdlib only."""

import sqlite3
from pathlib import Path

import pytest

from gridops import text2sql
from gridops.audit import AuditLog
from gridops.demo_helpers import ask, dispatch_plan, ensure_db, outage_summary
from gridops.dispatch import Crew, CrewRoster, NoCrewAvailable, dispatch, score_crew
from gridops.escalation import ConfirmationGate, tier_for_band
from gridops.feedback import FeedbackError, capture, list_feedback
from gridops.orchestrator import Orchestrator
from gridops.pii import scrub
from gridops.severity import classify
from gridops.sop_rag import SOPRAG
from gridops.storm import FakeStorm, LiveStormBackend, StormGap
from gridops.telemetry import build_db
from gridops.views import GatewayError, run_query, validate

ROOT = Path(__file__).resolve().parents[1]
SOPS = ROOT / "docs" / "sops"


@pytest.fixture()
def db(tmp_path):
    return str(build_db(tmp_path / "grid.db"))


# ---------- telemetry anchors (5) ----------

def test_anchor_outage_sev01(db):
    con = sqlite3.connect(db)
    row = con.execute(
        "SELECT customers_out, critical_facility_affected, etr_hours, cause"
        " FROM outages WHERE outage_id='OUT-SEV-01'").fetchone()
    con.close()
    assert row == (12400, 1, 8.0, "equipment-failure")


def test_anchor_storm_outage(db):
    con = sqlite3.connect(db)
    row = con.execute(
        "SELECT customers_out, etr_hours FROM outages WHERE outage_id='OUT-STORM-02'").fetchone()
    con.close()
    assert row == (3100, 6.0)


def test_anchor_crew_availability(db):
    con = sqlite3.connect(db)
    rows = dict(con.execute("SELECT crew_id, status FROM crews").fetchall())
    con.close()
    assert rows["CREW-A-07"] == "available"
    assert rows["CREW-B-09"] == "committed"


def test_anchor_load_anomaly_f114(db):
    con = sqlite3.connect(db)
    row = con.execute(
        "SELECT mw, baseline_mw FROM load_readings WHERE feeder_id='F-114'"
        " ORDER BY reading_id DESC LIMIT 1").fetchone()
    con.close()
    mw, base = row
    assert abs(mw / base - 1.38) < 0.01


def test_seed_determinism(tmp_path):
    p1 = build_db(tmp_path / "a.db")
    p2 = build_db(tmp_path / "b.db")
    c1 = sqlite3.connect(p1)
    c2 = sqlite3.connect(p2)
    n1 = c1.execute("SELECT COUNT(*) FROM outages").fetchone()
    n2 = c2.execute("SELECT COUNT(*) FROM outages").fetchone()
    r1 = c1.execute("SELECT mw FROM load_readings ORDER BY reading_id").fetchall()
    r2 = c2.execute("SELECT mw FROM load_readings ORDER BY reading_id").fetchall()
    c1.close()
    c2.close()
    assert n1 == n2 and r1 == r2


# ---------- gateway security (8) ----------

def test_gateway_allows_plain_select(db):
    cols, rows = run_query(db, "SELECT outage_id FROM v_active_outages")
    assert "outage_id" in cols and len(rows) > 0


def test_gateway_rejects_multi_statement(db):
    with pytest.raises(GatewayError) as e:
        validate("SELECT 1; SELECT 2")
    assert "SEC-SELECT-01" in str(e.value)


def test_gateway_rejects_non_select(db):
    with pytest.raises(GatewayError) as e:
        validate("DROP TABLE outages")
    assert "SEC-SELECT-01" in str(e.value)


def test_gateway_rejects_insert(db):
    with pytest.raises(GatewayError) as e:
        validate("INSERT INTO outages VALUES ('x')")
    assert "SEC-SELECT-01" in str(e.value)


def test_gateway_ignores_keywords_inside_literals(db):
    cols, rows = run_query(
        db, "SELECT outage_id FROM v_active_outages WHERE cause = 'drop table'")
    assert isinstance(rows, list)  # literal text must not trip the filter


def test_gateway_case_insensitive_select(db):
    cols, _ = run_query(db, "select outage_id from v_active_outages")
    assert "outage_id" in cols


def test_gateway_injects_limit(db):
    safe = validate("SELECT outage_id FROM v_active_outages")
    assert "LIMIT 100" in safe.upper()


def test_gateway_keeps_existing_limit(db):
    safe = validate("SELECT outage_id FROM v_active_outages LIMIT 5")
    assert safe.upper().count("LIMIT") == 1


# ---------- text2sql intents (7) ----------

def test_intent_outages():
    assert text2sql.detect_intent("which outages are active?") == "active_outages_by_severity"


def test_intent_crew():
    assert text2sql.detect_intent("show crew utilization") == "crew_utilization"


def test_intent_backlog():
    assert text2sql.detect_intent("what is the restoration backlog?") == "restoration_backlog"


def test_intent_load():
    assert text2sql.detect_intent("any load anomalies on feeders?") == "load_anomalies"


def test_intent_critical():
    assert text2sql.detect_intent("is the hospital affected?") == "critical_facility_exposure"


def test_intent_unknown_raises():
    with pytest.raises(text2sql.IntentNotFound):
        text2sql.detect_intent("what is the meaning of life?")


def test_answer_cites_rule_and_returns_rows(db):
    res = text2sql.answer(db, "list active outages")
    assert res["rule"] == "INTENT-OUT-01"
    assert len(res["rows"]) >= 2
    assert "OUT-SEV-01" in [r[0] for r in res["rows"]]


def test_answer_retry_then_escalate(db, monkeypatch):
    calls = []

    def fake(db_path, sql):
        calls.append(sql)
        if len(calls) == 1:
            raise sqlite3.OperationalError("boom")
        return (["c"], [(1,)])

    monkeypatch.setattr(text2sql, "run_query", fake)
    text2sql.answer(db, "active outages")
    assert len(calls) == 2  # exactly one retry

    def always_fail(db_path, sql):
        raise sqlite3.OperationalError("boom")

    monkeypatch.setattr(text2sql, "run_query", always_fail)
    with pytest.raises(text2sql.EscalationNeeded):
        text2sql.answer(db, "active outages")


# ---------- severity classifier (7) ----------

def test_severity_critical_anchor():
    r = classify("OUT-SEV-01", 12400, True, 8.0)
    assert r.band == "critical" and r.score == 12400 * 2.0 * 1.5


def test_severity_high():
    assert classify("X", 5000, False, 8.0).band == "high"


def test_severity_medium():
    assert classify("X", 3100, False, 6.0).band == "medium"


def test_severity_low():
    assert classify("X", 500, False, 2.0).band == "low"


def test_severity_band_boundary():
    assert classify("B", 10000, False, 1.0).band == "critical"
    assert classify("B", 9999, False, 1.0).band == "high"


def test_severity_critical_facility_doubles():
    assert classify("C", 5000, True, 1.0).band == "critical"
    assert classify("C", 5000, False, 1.0).band == "high"


def test_severity_rejects_negative():
    with pytest.raises(ValueError):
        classify("X", -5, False, 1.0)
    with pytest.raises(ValueError):
        classify("X", 5, False, -1.0)


def test_severity_breakdown_is_transparent():
    r = classify("OUT-SEV-01", 12400, True, 8.0)
    assert "12400" in r.breakdown and "critical" in r.breakdown


# ---------- dispatch optimizer (8) ----------

def _crew(cid, skills, km, shift="day", status="available"):
    return Crew(crew_id=cid, skills=tuple(skills), depot_km=km,
                shift=shift, status=status)


def test_dispatch_picks_closest_qualified():
    crews = [_crew("CREW-A-07", ("overhead", "switching"), 4.0),
             _crew("CREW-A-11", ("overhead",), 9.5)]
    best = dispatch(crews, {"overhead", "switching"}, "critical")
    assert best.crew_id == "CREW-A-07"


def test_dispatch_excludes_committed():
    crews = [_crew("CREW-B-09", ("overhead", "switching"), 1.0, status="committed"),
             _crew("CREW-A-11", ("overhead",), 9.5)]
    best = dispatch(crews, {"overhead"}, "high")
    assert best.crew_id == "CREW-A-11"


def test_dispatch_excludes_night_for_low_urgency():
    crews = [_crew("N1", ("overhead",), 1.0, shift="night")]
    with pytest.raises(NoCrewAvailable):
        dispatch(crews, {"overhead"}, "medium")


def test_dispatch_allows_night_for_critical():
    crews = [_crew("N1", ("overhead", "switching"), 2.0, shift="night")]
    best = dispatch(crews, {"overhead"}, "critical")
    assert best.crew_id == "N1"


def test_dispatch_no_crew_raises():
    with pytest.raises(NoCrewAvailable):
        dispatch([], {"overhead"}, "critical")


def test_dispatch_breakdown_transparent():
    a = score_crew(_crew("CREW-A-07", ("overhead", "switching"), 4.0),
                   {"overhead", "switching"}, "critical")
    assert a is not None
    assert a.crew_id in a.breakdown and "84.0" in a.breakdown
    assert abs(a.score - (0.45 * 84.0 + 0.35 * 100.0 + 0.20 * 100.0)) < 0.01


def test_dispatch_skill_partial_credit():
    a = score_crew(_crew("P1", ("overhead",), 0.0), {"overhead", "switching"}, "high")
    assert a is not None and a.skill_points == 50.0


def test_roster_from_rows(db):
    con = sqlite3.connect(db)
    rows = con.execute(
        "SELECT crew_id, skills, depot_substation, depot_km_from_f101,"
        " shift, status FROM crews").fetchall()
    con.close()
    roster = CrewRoster.from_rows(rows)
    assert len(roster.crews) == 6
    assert any(c.crew_id == "CREW-A-07" for c in roster.crews)


# ---------- storm signal (3) ----------

def test_fake_storm_deterministic():
    cells = FakeStorm().cells_for_area("north")
    assert len(cells) == 1 and cells[0].cell_id == "STORM-09"


def test_live_storm_unconfigured_is_gap():
    res = LiveStormBackend().cells_for_area("north")
    assert isinstance(res, StormGap) and res.is_gap
    assert "not configured" in res.reason


def test_live_storm_gap_names_what_is_missing():
    res = LiveStormBackend().cells_for_area("north")
    assert "api_key" in res.detail  # tells the operator how to go live


# ---------- SOP RAG (4) ----------

def test_rag_finds_dispatch_sop():
    rag = SOPRAG(SOPS)
    hits = rag.search("how are crews scored for dispatch?")
    assert hits and hits[0].citation.startswith("sop-02-crew-dispatch.md §")


def test_rag_finds_blackout_sop():
    rag = SOPRAG(SOPS)
    hits = rag.search("do rolling blackouts need human confirmation?")
    assert hits and hits[0].citation.startswith("sop-03-load-management.md §")


def test_rag_not_found_is_explicit():
    rag = SOPRAG(SOPS)
    res = rag.answer("quantum cryptography key rotation policy")
    assert res["found"] is False and "Escalated" in res["message"]


def test_rag_citation_format():
    rag = SOPRAG(SOPS)
    hits = rag.search("restoration order after a fault")
    assert hits and "§" in hits[0].citation


# ---------- escalation tiers & gates (8) ----------

def test_tier_mapping():
    assert tier_for_band("critical") == "T1"
    assert tier_for_band("high") == "T2"
    assert tier_for_band("medium") == "T3"
    assert tier_for_band("low") == "T4"


def test_tier_unknown_band():
    with pytest.raises(ValueError):
        tier_for_band("extreme")


def test_blackout_always_gated():
    g = ConfirmationGate()
    assert g.requires_confirmation("rolling-blackout", "T4") is True
    assert g.requires_confirmation("mutual-aid-request", "T4") is True


def test_t1_dispatch_gated_t4_not():
    g = ConfirmationGate()
    assert g.requires_confirmation("crew-dispatch", "T1") is True
    assert g.requires_confirmation("crew-dispatch", "T4") is False


def test_gate_approve_and_deny():
    g = ConfirmationGate()
    assert g.decide("a1", True, "Duty Officer") == "approved"
    assert g.decide("a2", False, "Duty Officer") == "denied"
    assert g.status("a9") == "pending"


def test_gate_requires_approver_name():
    g = ConfirmationGate()
    with pytest.raises(ValueError):
        g.decide("a1", True, "  ")


# ---------- audit chain (3) ----------

def test_audit_chain_verifies():
    log = AuditLog()
    log.record("dispatch", {"crew": "CREW-A-07"})
    log.record("restore", {"feeder": "F-101"})
    assert log.verify_chain() is True


def test_audit_tamper_detected():
    log = AuditLog()
    log.record("dispatch", {"crew": "CREW-A-07"})
    log.records[0]["details"]["crew"] = "CREW-X-99"
    assert log.verify_chain() is False


def test_audit_seq_increments():
    log = AuditLog()
    assert log.record("a")["seq"] == 0
    assert log.record("b")["seq"] == 1


# ---------- PII scrubbing + feedback (8) ----------

def test_scrub_email_phone_ssn():
    cleaned, n = scrub("call me at 555-123-4567 or joe@example.com, ssn 123-45-6789")
    assert n == 3
    assert "[PHONE]" in cleaned and "[EMAIL]" in cleaned and "[SSN]" in cleaned
    assert "555-123-4567" not in cleaned


def test_scrub_clean_text_untouched():
    cleaned, n = scrub("feeder F-101 restored at noon")
    assert n == 0 and cleaned == "feeder F-101 restored at noon"


def test_feedback_capture_and_list():
    log = AuditLog()
    capture(log, session_id="s1", turn_id="t1", rating="up")
    capture(log, session_id="s1", turn_id="t2", rating="down",
            correction="wrong crew, send CREW-A-07")
    all_fb = list_feedback(log)
    assert len(all_fb) == 2
    assert len(list_feedback(log, session_id="s1")) == 2
    assert len(list_feedback(log, session_id="nope")) == 0


def test_feedback_scrubs_pii_before_storage():
    log = AuditLog()
    capture(log, session_id="s1", turn_id="t1", rating="down",
            correction="call 555-123-4567 about outage")
    stored = list_feedback(log)[0]["details"]
    assert stored["pii_redactions"] == 1
    assert "555-123-4567" not in stored["correction"]
    assert "[PHONE]" in stored["correction"]


def test_feedback_rejects_bad_input():
    log = AuditLog()
    with pytest.raises(FeedbackError):
        capture(log, session_id="", turn_id="t1", rating="up")
    with pytest.raises(FeedbackError):
        capture(log, session_id="s1", turn_id="t1", rating="maybe")
    with pytest.raises(FeedbackError):
        capture(log, session_id="s1", turn_id="t1", rating="down", correction="  ")


def test_feedback_tamper_breaks_chain():
    log = AuditLog()
    capture(log, session_id="s1", turn_id="t1", rating="up")
    log.records[0]["details"]["rating"] = "down"
    assert log.verify_chain() is False


# ---------- orchestrator (6) ----------

def test_orchestrator_fan_out(db):
    orch = Orchestrator(db, SOPS)
    res = orch.handle("which outages are active and which crew should be dispatched?")
    assert "outages" in res["subtasks"] and "dispatch" in res["subtasks"]
    assert res["dispatch"]["assignment"]["crew"] == "CREW-A-07"


def test_orchestrator_unknown_escalates(db):
    orch = Orchestrator(db, SOPS)
    res = orch.handle("what is the meaning of life?")
    assert res["answer"] == "escalated"


def test_orchestrator_storm_subtask(db):
    orch = Orchestrator(db, SOPS)
    res = orch.handle("is there a storm coming?")
    assert "storm" in res["subtasks"]
    assert res["tier"] == "T2"


def test_orchestrator_sop_subtask(db):
    orch = Orchestrator(db, SOPS)
    res = orch.handle("what is our sop for crew dispatch?")
    assert res["sop"]["found"] is True


def test_orchestrator_dispatch_severity_breakdown(db):
    orch = Orchestrator(db, SOPS)
    d = orch._dispatch_advice("dispatch a crew")
    assert d["severity"] == "critical"
    assert "12400" in d["severity_breakdown"]
    assert d["tier"] == "T1"


# ---------- demo helpers (3) ----------

def test_demo_outage_summary(tmp_path):
    db_path = ensure_db(tmp_path / "demo.db")
    rows = outage_summary(db_path)
    assert any(r["outage_id"] == "OUT-SEV-01" for r in rows)


def test_demo_dispatch_plan(tmp_path):
    db_path = ensure_db(tmp_path / "demo.db")
    plan = dispatch_plan(db_path)
    assert plan["crew"] == "CREW-A-07"
    assert plan["tier"] == "T1"
    assert plan["severity"] == "critical"


def test_demo_ask(tmp_path):
    db_path = ensure_db(tmp_path / "demo.db")
    res = ask(db_path, SOPS, "show active outages")
    assert "outages" in res["subtasks"]


# ---------- review fixes (grokbot-portfolio, 2026-10-18) ----------

def test_unqualified_crew_never_wins_on_proximity():
    crews = [Crew("C-NEAR", ("vegetation",), 0.0, "day", "available"),
             Crew("C-FAR", ("overhead", "switching"), 25.0, "day", "available")]
    assert dispatch(crews, {"overhead", "switching"}, "critical").crew_id == "C-FAR"


def test_only_unqualified_crews_raises():
    crews = [Crew("C-NEAR", ("vegetation",), 0.0, "day", "available")]
    with pytest.raises(NoCrewAvailable):
        dispatch(crews, {"overhead"}, "critical")


def test_day_shift_preferred_over_night_for_critical():
    day = score_crew(Crew("D", ("overhead",), 5.0, "day", "available"), {"overhead"}, "critical")
    night = score_crew(Crew("N", ("overhead",), 5.0, "night", "available"), {"overhead"}, "critical")
    assert day.sla_points == 100.0 and night.sla_points == 70.0 and day.score > night.score


def test_critical_facility_is_never_below_high():
    r = classify("OUT-X", 150, True, 2.0)
    assert r.band == "high" and "floor" in r.breakdown
    assert classify("OUT-Y", 150, False, 2.0).band == "low"


def test_scrub_parenthesised_phone():
    cleaned, n = scrub("call (555) 123-4567")
    assert cleaned == "call [PHONE]" and n == 1

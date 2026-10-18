# Grid Outage Operations Agents

> **Recruiter summary:** End-to-end agentic operations for a fictional
> electric utility — outage triage, crew dispatch, load-anomaly detection,
> and restoration tracking. Deterministic and auditable: read-only
> text-to-SQL over synthetic grid telemetry, a transparent crew-dispatch
> optimizer (proximity × skill × SLA, scored 92.8 for the anchor outage),
> and human confirmation gates on every risky action. **95 tests green**,
> stdlib only, no model required.

## Problem → approach → outcome

Grid operators triage outages under time pressure: which fault matters
most, who goes where, and what needs a human. This repo makes that loop
executable — synthetic telemetry, a severity classifier, a dispatch
optimizer with printed scoring breakdowns, SOP-grounded answers with
citations, and a hash-chained audit trail. The patterns (guardrails,
escalation tiers, eval-style regression checks) transfer directly to a
production ADMS integration; only the data source and the planner change.

## How it works

1. `gridops/telemetry.py` builds a deterministic SQLite database (seed 42):
   substations, feeders, outages, crews, load readings.
2. The ReAct orchestrator decomposes a question into sub-tasks and routes
   each to one tool — never guessing, escalating when nothing matches.
3. Text-to-SQL runs through a SELECT-only gateway
   (`SEC-SELECT-01/02/03`, plus `SEC-SELECT-04`: views only, enforced by a
   SQLite authorizer); one simplified retry, then escalation.
4. The severity classifier and dispatch optimizer score live rows with
   transparent breakdowns.
5. T1–T4 tiers and confirmation gates decide what needs a human.
6. Every action and feedback event lands in the hash-chained audit log.

## Real code, real output

```python
from gridops import demo_helpers as H
db = H.ensure_db("grid.db")
plan = H.dispatch_plan(db)
print(plan["severity_breakdown"])
print(plan["crew"], plan["score"], plan["tier"])
```

```
12400 customers x 2.0 (critical facility) x 1.5 (ETR 8.0h) = 37200 -> critical
CREW-A-07 92.8 T1
```

The full assignment breakdown:

```
CREW-A-07: proximity 84.0 (depot 4.0 km) x0.45 + skill 100.0 (matched ['overhead', 'switching']) x0.35 + sla 100.0 x0.20 = 92.8
```

## Modules

| Module | What it does |
|---|---|
| `telemetry.py` | Seeded SQLite grid data + deterministic anchors |
| `views.py` | 4 read-only views; SELECT-only gateway (cited rule IDs) |
| `text2sql.py` | 5 intents, one retry, then escalate |
| `severity.py` | **Differentiator:** outage-severity classifier with breakdown |
| `dispatch.py` | **Differentiator:** crew-dispatch optimizer (proximity × skill × SLA) |
| `storm.py` | Fake/live storm signal; explicit gap, never hallucinates |
| `sop_rag.py` | TF-IDF over 4 SOPs, `<file> §<section>` citations |
| `orchestrator.py` | ReAct fan-out across tools |
| `escalation.py` | T1–T4 tiers + confirmation gates |
| `audit.py` | Hash-chained log, tamper detection |
| `feedback.py` / `pii.py` | Thumbs/corrections, PII-scrubbed before storage |
| `demo_helpers.py` | Tested logic behind the Streamlit demo |

## How this differs from coldchain/retail

Cold-chain tracks reefer telemetry and temperature compliance; retail
tracks stores, SKUs, and suppliers. This repo operates a power grid, and the
code that only exists here is:

- `severity.py`: customers out x critical-facility multiplier x long-ETR
  multiplier, banded, with a critical-facility floor at "high".
- `dispatch.py`: a weighted crew score (0.45 proximity, 0.35 skill, 0.20
  shift/SLA) that excludes crews with none of the required skills, off-duty
  crews, and night crews for medium/low outages, and prints its arithmetic.
- `v_load_anomalies`: feeders running 25%+ over baseline, and a storm-cell
  feed that degrades to an explicit gap.

The shared spine (gateway, RAG, audit, feedback) is deliberate; none of the
domain logic is shared with the other two.

## Run it

```bash
python3 -m pytest tests/ -q        # 95 tests, stdlib only
python3 scripts/count_tests.py     # prints the real total
pip install streamlit              # optional, demo only
streamlit run demo/app.py
```

## Guardrails and security controls

- SQL gateway: SELECT-only, cited rule IDs, views only (SQLite authorizer,
  ADR 0001), 100-row cap enforced at fetch time, literals stripped before
  keyword scanning.
- Rolling blackouts and mutual-aid requests always need human
  confirmation; crews matching none of the required skills are never
  dispatched (tested).
- ETRs are never published before a crew confirms the cause on site.
- Feedback free text is PII-scrubbed (email/phone/SSN) before storage.
- Audit chain is tamper-evident (`verify_chain()`).
- See `docs/threat-model.md` (STRIDE-lite) and `knowledge/`.

## Limitations and known failures

- Intents are keyword rules, not an LLM planner — paraphrased questions
  outside the keyword sets escalate (tested as `IntentNotFound`).
- TF-IDF RAG has no stemming; singular/plural mismatches can misrank
  (documented, not hidden).
- The storm "live" backend is a stub returning an explicit gap.
- Dispatch advice always targets the anchor outage (OUT-SEV-01), and crew
  distances are stored from feeder F-101 only (`depot_km_from_f101`); a
  per-outage distance table is needed before advising on other outages.
- A crew matching some but not all required skills can still be chosen
  (partial skill points); a stricter carrier would make every skill mandatory.
- The 95 tests are regression checks on synthetic data, not quality
  claims about real grid operations.

## Standardization review (2026-10-18)

Reviewed against the portfolio standard after the build. Bugs found and fixed, each now pinned by a test:

1. **An unqualified crew could win on proximity.** The README said "unqualified crews are never dispatched", but a crew with none of the required skills still scored 0.45 x proximity + 0.20 x SLA: a vegetation crew at 0 km (65.0) beat a fully skilled line crew at 25 km (55.0). Crews matching no required skill are now excluded; if none qualify, `NoCrewAvailable` is raised.
2. **The 0.20 SLA term was a constant 100.** Night crews are now 70 points (accepted for critical/high only), so a day crew is preferred at equal distance.
3. **A hospital outage could be rated "low".** 150 customers x 2.0 = 300 fell below the medium band. An outage affecting a critical facility is now never below "high", and the breakdown says when the floor applied.
4. **PII scrubber missed `(555) 123-4567`.** The phone pattern needed a word boundary before `(`; replaced with a lookbehind pattern that also takes a `+1` prefix.
5. **Gateway had no view allowlist.** It blocked writes but any base table or `sqlite_master` was readable through the planner path, and a caller-supplied `LIMIT 100000` skipped the 100-row cap. New rule `SEC-SELECT-04` is enforced by a SQLite authorizer (`authz.py`, ADR 0001), and rows past 100 are never fetched.

Differentiator on the seeded data (regenerated and checked by CI on every push):

<!-- run: python scripts/show_differentiator.py -->
```text
12400 customers x 2.0 (critical facility) x 1.5 (ETR 8.0h) = 37200 -> critical
CREW-A-07 92.8 T1
150 customers x 2.0 (critical facility) x 1.0 (ETR 2.0h) = 300 -> high (critical-facility floor)
chosen: CREW-LINE
NoCrewAvailable: no available crew with skills=['overhead'] for severity=critical
```
<!-- /run -->

Test count (also checked by CI):

<!-- run: python scripts/count_tests.py -->
```text
95 tests collected
```
<!-- /run -->

### Authorizer template sync (2026-10-18)

The SQLite authorizer was updated to the shared strict, view-aware version.
A base-table read is allowed only when SQLite reports it on behalf of one of
the allowed views (the authorizer's view-name argument). A read with no view
name is denied. `sqlite_master` is always denied, even if listed, and so is
`load_extension`. The old version falsely denied a self-join of `v_crew_status`; a regression test covers it.
`tests/test_authorizer_sync.py` drives the authorizer directly, independent
of the text check. It covers comma joins and comment-obfuscated joins with a
base table, every view, and view self-joins.

Known residual: a read that uses no columns of a table behind a view is
allowed, because SQLite reports the unused side of a view self-join the same
way. So `SELECT count(*) FROM <that table>` or `EXISTS (SELECT 1 FROM ...)`
can still reveal a row count, but no column data. Any column reference is
denied.

## Built vs planned

| Status | Item |
|---|---|
| Built | Telemetry, views+gateway, text-to-SQL, severity, dispatch, storm, RAG, orchestrator, tiers+gates, audit, PII-scrubbed feedback, demo, docs |
| Built | CI on every push: ruff, tests, docs drift check, hashed brand check, gitleaks; CodeQL; Dependabot |
| Planned | Live storm-provider wiring, embeddings-based RAG, ADMS replica integration |

## Related repos

- [Jagadish-coldchain-logistics-agents](https://github.com/jagadishmazure-jpg/Jagadish-coldchain-logistics-agents), [Jagadish-retail-ops-agents](https://github.com/jagadishmazure-jpg/Jagadish-retail-ops-agents): same spine, other domains
- [Jagadish-telecom-incident-agents](https://github.com/jagadishmazure-jpg/Jagadish-telecom-incident-agents): field dispatch with a hard skill filter, for comparison
- [Jagadish-event-driven-agents](https://github.com/jagadishmazure-jpg/Jagadish-event-driven-agents): reacting to telemetry events

## Docs

- `docs/adr/0001-sqlite-authorizer-backstop.md`

- `knowledge/domain-notes.md`, `knowledge/architecture.md` (Mermaid)
- `docs/implementation-guide.md`, `docs/interview-points.md`,
  `docs/threat-model.md`, `docs/sops/` (4 SOPs)

---

*All data is synthetic and fictional ("Lakeshore Power & Light"). This is
an independent portfolio project, not affiliated with any utility.*

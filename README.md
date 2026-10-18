# Grid Outage Operations Agents

> **Recruiter summary:** End-to-end agentic operations for a fictional
> electric utility — outage triage, crew dispatch, load-anomaly detection,
> and restoration tracking. Deterministic and auditable: read-only
> text-to-SQL over synthetic grid telemetry, a transparent crew-dispatch
> optimizer (proximity × skill × SLA, scored 92.8 for the anchor outage),
> and human confirmation gates on every risky action. **67 tests green**,
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
   (`SEC-SELECT-01/02/03`); one simplified retry, then escalation.
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
tracks stores, SKUs, and suppliers. This repo operates a power grid:
outage severity classification, skill-constrained crew dispatch, load
anomaly detection, and storm-driven escalation — none of which exist in
the other two. The shared spine (gateway, RAG, audit, feedback) is
deliberate; the domain logic is not shared.

## Run it

```bash
python3 -m pytest tests/ -q        # 67 tests, stdlib only
python3 scripts/count_tests.py     # prints the real total
pip install streamlit              # optional, demo only
streamlit run demo/app.py
```

## Guardrails and security controls

- SQL gateway: SELECT-only, cited rule IDs, 100-row cap, literals
  stripped before keyword scanning.
- Rolling blackouts and mutual-aid requests always need human
  confirmation; unqualified crews are never dispatched.
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
- The 67 tests are regression checks on synthetic data, not quality
  claims about real grid operations.

## Built vs planned

| Status | Item |
|---|---|
| Built | Telemetry, views+gateway, text-to-SQL, severity, dispatch, storm, RAG, orchestrator, tiers+gates, audit, PII-scrubbed feedback, demo, docs |
| Written, not run | `.github/workflows/ci.yml` (local only; the GitHub App returns 403 on workflow files — added at standardization) |
| Planned | Live storm-provider wiring, embeddings-based RAG, ADMS replica integration |

## Docs

- `knowledge/domain-notes.md`, `knowledge/architecture.md` (Mermaid)
- `docs/implementation-guide.md`, `docs/interview-points.md`,
  `docs/threat-model.md`, `docs/sops/` (4 SOPs)

---

*All data is synthetic and fictional ("Lakeshore Power & Light"). This is
an independent portfolio project, not affiliated with any utility.*

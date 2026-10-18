# Implementation guide

For adopters who want to run or extend this repo.

## Run it

```bash
python3 -m pytest tests/ -q        # full suite, stdlib only
python3 scripts/count_tests.py     # prints the real test total
```

Optional demo UI:

```bash
pip install streamlit
streamlit run demo/app.py
```

## Going live (what changes)

| Scaffold (this repo) | Production path |
|---|---|
| Seeded SQLite | Outage-management system / ADMS replica |
| Keyword intents | LLM planner with constrained output |
| TF-IDF RAG | Embeddings + reranker, versioned SOP corpus |
| FakeStorm | Weather-provider API via `LiveStormBackend` |
| In-memory audit | Append-only store (e.g. WORM bucket) |
| `ConfirmationGate.decide()` | Ticketing/HITL integration |

## Key files

- `gridops/telemetry.py` — regenerate data: `build_db(path)` (seed 42).
- `gridops/dispatch.py` — retune weights (0.45/0.35/0.20) per utility policy.
- `gridops/severity.py` — retune bands/thresholds per regulator rules.
- `gridops/views.py` — gateway rules SEC-SELECT-01/02/03/04 (04 = views only,
  enforced by `gridops/authz.py`).

# Architecture

```mermaid
flowchart TB
    subgraph Sources
        DB[(SQLite telemetry<br/>substations, feeders, outages,<br/>crews, load readings)]
        SOP[4 SOP docs]
        WX[Storm signal<br/>fake / live-gap]
        OP[Operator question]
    end

    subgraph Agent
        ORCH[ReAct orchestrator<br/>multi-intent fan-out]
        T2S[Text-to-SQL<br/>SELECT-only gateway<br/>SEC-SELECT-01/02/03]
        SEV[Severity classifier<br/>customers × critical × ETR]
        DSP[Crew-dispatch optimizer<br/>proximity × skill × SLA]
        RAG[TF-IDF SOP RAG<br/>cited answers]
    end

    subgraph Controls
        TIER[T1–T4 escalation]
        GATE[Confirmation gates<br/>blackouts, mutual aid]
        AUDIT[Hash-chained audit]
        FB[Feedback + PII scrub]
    end

    OP --> ORCH
    ORCH --> T2S --> DB
    ORCH --> SEV
    ORCH --> DSP
    ORCH --> RAG --> SOP
    ORCH --> WX
    SEV --> TIER
    DSP --> TIER
    TIER --> GATE
    ORCH --> AUDIT
    FB --> AUDIT
```

## Data flow

1. `telemetry.build_db()` generates the deterministic SQLite database.
2. The orchestrator decomposes a question into sub-tasks and routes each
   to one tool; the SQL gateway enforces read-only access.
3. Severity classification and dispatch optimization run on live rows.
4. Tiers and confirmation gates decide what needs a human.
5. Every action and every feedback event lands in the hash-chained audit.

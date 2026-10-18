# Threat model (STRIDE-lite)

| Threat | Mitigation in this repo |
|---|---|
| **S**poofing — fake outage reports | Sensor reports outrank customer calls (SOP-01); gateway is read-only so reports can't be forged via the agent |
| **T**ampering — altering the audit trail | Hash-chained audit; `verify_chain()` detects any modification |
| **R**epudiation — "I never approved that" | ConfirmationGate records approver name per action in the audit log |
| **I**nformation disclosure — PII in feedback | `pii.scrub()` redacts email/phone/SSN before storage; error paths never echo row data |
| **D**enial of service — runaway queries | 100-row cap enforced at fetch time; single-statement rule; one retry then escalate |
| **E**levation — agent issuing risky orders | Rolling blackouts + mutual aid always need human confirmation; crews with none of the required skills are never dispatched (tested since the 2026-10-18 review) |

## LLM-specific (OWASP LLM Top 10, where applicable)

- **Prompt injection:** the text-to-SQL layer uses keyword intents + fixed
  templates, not free-form generation — injected text can't become SQL.
- **Excessive agency:** the agent cannot write to the database at all
  (SEC-SELECT-01/02) and only the views are readable (SEC-SELECT-04, SQLite authorizer); physical actions are confirmation-gated.
- **Misinformation:** storm signal returns an explicit gap when live data
  is missing; SOP RAG returns not-found instead of inventing procedure.

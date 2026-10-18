# Domain notes — grid outage operations

Distilled notes on how electric-utility outage operations work, written to
explain the design choices in this repo. All entities are fictional.

## The operations loop

1. **Detect** — sensors, customer calls, and crew reports feed the outage
   management system. Sensor reports outrank customer calls for confirmation.
2. **Triage** — each outage is scored (customers × critical-facility factor
   × restoration-time factor) into critical/high/medium/low, which maps to
   escalation tiers T1–T4.
3. **Dispatch** — eligible crews are scored on proximity, skill match, and
   shift/SLA fit. Required skills derive from the cause: overhead faults
   need overhead certification; switching operations need switching
   certification. Unqualified crews are never assigned — the duty officer
   is escalated instead.
4. **Restore** — critical facilities first, then the largest customer
   blocks. Crews confirm the fault is cleared before re-energizing.
5. **Review** — every T1 outage gets an after-action review.

## Why the differentiators matter

- **Crew-dispatch optimizer:** during storms, dispatchers juggle dozens of
  outages and crews under time pressure. A transparent scoring breakdown
  (proximity × skill × SLA) makes the recommendation auditable — an
  operator can see *why* crew A beat crew B instead of trusting a black box.
- **Severity classifier:** consistent triage is the difference between a
  hospital waiting 8 hours and 30 minutes. The multiplicative formula
  encodes the industry practice of weighting critical facilities heavily.

## Guardrails that are load-bearing, not decorative

- Rolling blackouts and mutual-aid requests always need human confirmation.
- ETRs are never published before a crew confirms the cause on site.
- Feedback text is PII-scrubbed before it reaches the audit log.
- The SQL gateway is SELECT-only with cited rule IDs; the agent gets one
  retry, then escalates.

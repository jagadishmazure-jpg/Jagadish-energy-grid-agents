# Interview points

## The one-liner
Deterministic, auditable grid-outage operations: synthetic telemetry,
read-only text-to-SQL, a transparent crew-dispatch optimizer, and
human gates on every risky action — no model needed to prove the pattern.

## Talking points

1. **Differentiator depth:** the dispatch optimizer scores
   proximity × skill × SLA with a printed breakdown — operators audit the
   *why*, not just the *who*. The severity classifier encodes the
   industry practice of weighting critical facilities multiplicatively.
2. **Safety by construction:** SELECT-only gateway with cited rule IDs,
   one retry then escalate, confirmation gates on blackouts and mutual
   aid, hash-chained audit, PII-scrubbed feedback.
3. **Honest evals:** every number in the README comes from a real run;
   the suite is regression checks, not quality claims.
4. **Failure modes handled:** no qualified crew → escalate, don't guess;
   live storm feed missing → explicit gap, never a hallucinated forecast;
   tampered audit → chain verification fails loudly.

## Questions this repo answers well

- "How do you keep an agent from doing something dangerous?" → gates +
  tiers + audit, each tested.
- "How do you make agent decisions explainable?" → scoring breakdowns
  and cited rule traces everywhere.
- "What breaks in production?" → see Limitations in the README.

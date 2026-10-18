# Security policy

## Reporting
Please report vulnerabilities via GitHub's private vulnerability reporting
on this repo. Do not open public issues for security bugs.

## Scope
This is a synthetic demo: all data is fictional, there is no production
system, and no real credentials exist in the repo. The controls below are
the ones the code actually implements and tests:

- SELECT-only SQL gateway (SEC-SELECT-01/02/03), 100-row cap
- Confirmation gates on rolling blackouts and mutual-aid requests
- Hash-chained audit log with tamper detection
- PII scrubbing on free-text feedback before storage
- No secrets in code, data, or docs

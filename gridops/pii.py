"""PII scrubbing for free-text feedback.

Email addresses, phone numbers, and SSN-like patterns are replaced with
typed placeholders before storage. scrub() returns (cleaned, count) so
callers can audit how much was redacted.
"""

from __future__ import annotations

import re

_PATTERNS = [
    (re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+"),
     "[EMAIL]"),
    (re.compile(r"\b\d{3}[-.\s]?\d{3}[-.\s]?\d{4}\b"), "[PHONE]"),
    (re.compile(r"\b\d{3}-\d{2}-\d{4}\b"), "[SSN]"),
    (re.compile(r"\b\d{4}[- ]?\d{4}[- ]?\d{4}[- ]?\d{4}\b"), "[ACCOUNT]"),
]


def scrub(text: str) -> tuple[str, int]:
    """Redact PII patterns. Returns (cleaned_text, redaction_count)."""
    count = 0
    cleaned = text or ""
    for pattern, placeholder in _PATTERNS:
        cleaned, n = pattern.subn(placeholder, cleaned)
        count += n
    return cleaned, count

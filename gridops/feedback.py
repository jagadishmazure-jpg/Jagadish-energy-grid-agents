"""User feedback capture with PII scrubbing.

Thumbs up/down plus free-text corrections. Free text is PII-scrubbed
*before* storage (the gap grokbot-portfolio caught on sibling repos:
raw feedback text must never reach the audit log). Every record carries
session/turn linkage and is appended to the hash-chained audit log.
"""

from __future__ import annotations

from .audit import AuditLog
from .pii import scrub


class FeedbackError(ValueError):
    """Raised for malformed feedback."""


VALID_RATINGS = ("up", "down")


def capture(audit: AuditLog, *, session_id: str, turn_id: str,
            rating: str, correction: str = "") -> dict:
    """Capture one feedback event. Returns the stored record summary."""
    if not session_id or not session_id.strip():
        raise FeedbackError("session_id is required")
    if not turn_id or not turn_id.strip():
        raise FeedbackError("turn_id is required")
    if rating not in VALID_RATINGS:
        raise FeedbackError(f"rating must be one of {VALID_RATINGS}")
    if rating == "down" and not correction.strip():
        raise FeedbackError("thumbs-down requires a non-blank correction")
    cleaned, redactions = scrub(correction)
    entry = audit.record("user_feedback", {
        "session_id": session_id,
        "turn_id": turn_id,
        "rating": rating,
        "correction": cleaned,
        "pii_redactions": redactions,
    })
    return {"seq": entry["seq"], "rating": rating,
            "pii_redactions": redactions}


def list_feedback(audit: AuditLog, session_id: str | None = None) -> list[dict]:
    """List feedback records, optionally filtered to one session."""
    out = []
    for r in audit.records:
        if r["action"] != "user_feedback":
            continue
        if session_id and r["details"]["session_id"] != session_id:
            continue
        out.append(r)
    return out

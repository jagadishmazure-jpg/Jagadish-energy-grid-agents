"""Hash-chained audit log.

Each record's hash = sha256(prev_hash + canonical_json(record)), so any
tampering with an earlier record breaks every later link. verify_chain()
returns True only for an intact chain.
"""

from __future__ import annotations

import hashlib
import json
import time


def _canonical(record: dict) -> str:
    return json.dumps(record, sort_keys=True, separators=(",", ":"))


class AuditLog:
    def __init__(self) -> None:
        self.records: list[dict] = []
        self._prev = "GENESIS"

    def record(self, action: str, details: dict | None = None) -> dict:
        entry = {
            "seq": len(self.records),
            "ts": time.time(),
            "action": action,
            "details": details or {},
            "prev": self._prev,
        }
        entry["hash"] = hashlib.sha256(
            (self._prev + _canonical({k: v for k, v in entry.items()
                                     if k != "hash"})).encode()
        ).hexdigest()
        self._prev = entry["hash"]
        self.records.append(entry)
        return entry

    def verify_chain(self) -> bool:
        prev = "GENESIS"
        for entry in self.records:
            if entry["prev"] != prev:
                return False
            recomputed = hashlib.sha256(
                (prev + _canonical({k: v for k, v in entry.items()
                                   if k != "hash"})).encode()
            ).hexdigest()
            if recomputed != entry["hash"]:
                return False
            prev = entry["hash"]
        return True

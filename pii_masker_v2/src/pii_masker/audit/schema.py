"""Derive the audit row schema from the AuditEvent dataclass.

v2 contract: `AUDIT_FIELDNAMES` is NOT hand-maintained. Adding a field to
`AuditEvent` automatically adds it to the CSV header, the JSONL key order,
and the schema registry.
"""
from __future__ import annotations

import dataclasses
from typing import Any

from pii_masker.audit.event import AuditEvent

# Ordered tuple of field names, derived once at import time.
AUDIT_FIELDNAMES: tuple[str, ...] = tuple(
    f.name for f in dataclasses.fields(AuditEvent)
)


def event_as_dict(event: AuditEvent) -> dict[str, Any]:
    """Serialize an AuditEvent to a plain dict suitable for CSV/JSONL sinks.

    Enum values are unwrapped to strings. Everything else round-trips via
    `dataclasses.asdict` semantics.
    """
    row: dict[str, Any] = {}
    for f in dataclasses.fields(event):
        val = getattr(event, f.name)
        # Both EntityType and UsabilityTag inherit from str → val.value gives
        # the canonical string form for serialization.
        if hasattr(val, "value"):
            row[f.name] = val.value
        else:
            row[f.name] = val
    return row

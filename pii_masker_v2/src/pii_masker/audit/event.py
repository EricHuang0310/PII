"""AuditEvent — the single source of truth for the audit row schema.

v3/v4 had a hand-maintained `AUDIT_FIELDNAMES` list in `config.py` that had
to stay in sync with `AuditLogger.log_v3`. v2 derives the field list from
this dataclass — one source, no drift.
"""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field

from pii_masker.domain.entity_type import EntityType
from pii_masker.usability.tags import UsabilityTag


@dataclass(frozen=True, slots=True)
class AuditEvent:
    """One audit row — structured, versioned, joinable by span_id.

    v2 enhancements over the v3/v4 row:
    - `span_id` (stable UUID) replaces the ephemeral `id()` join key
    - `policy_version` + `pipeline_version` travel with every row
    - `detector_id` + `detector_version` are explicit (not derived from
      a `pattern_name` string)
    - `trace_id` ties all events from one mask() call together
    """

    session_id: str
    trace_id: str
    turn_id: str
    step: str
    rule_triggered: str
    entity_type: EntityType
    entity_subtype: str
    original_type_desc: str
    span_id: str
    start: int
    end: int
    score: float
    token_applied: str
    conflict_resolved: bool
    diarization_available: bool
    usability_tag: UsabilityTag
    detector_id: str
    policy_version: str
    pipeline_version: str
    timestamp: str = field(
        default_factory=lambda: dt.datetime.now(dt.UTC).isoformat()
    )

"""Tests for AuditEvent and derived schema."""
from __future__ import annotations

import pytest

from pii_masker.audit.event import AuditEvent
from pii_masker.audit.schema import AUDIT_FIELDNAMES, event_as_dict
from pii_masker.domain.entity_type import EntityType
from pii_masker.usability.tags import UsabilityTag


def _make_event() -> AuditEvent:
    return AuditEvent(
        session_id="S001",
        trace_id="trace-abc",
        turn_id="turn-01",
        step="Step1-5",
        rule_triggered="TW_PHONE",
        entity_type=EntityType.TW_PHONE,
        entity_subtype="MOBILE",
        original_type_desc="手機號碼",
        span_id="span-xyz",
        start=5,
        end=15,
        score=0.95,
        token_applied="[PHONE]",
        conflict_resolved=False,
        diarization_available=True,
        usability_tag=UsabilityTag.USABLE,
        detector_id="regex:tw_phone:v1",
        policy_version="v4.1.0",
        pipeline_version="2.0.0",
    )


@pytest.mark.unit
def test_audit_event_is_frozen() -> None:
    e = _make_event()
    with pytest.raises(Exception):
        e.session_id = "other"  # type: ignore[misc]


@pytest.mark.unit
def test_audit_event_timestamp_auto_populated() -> None:
    e = _make_event()
    assert e.timestamp  # ISO-formatted, non-empty


@pytest.mark.unit
def test_fieldnames_derived_from_dataclass() -> None:
    """AUDIT_FIELDNAMES must exactly match AuditEvent fields in declaration order."""
    expected = (
        "session_id", "trace_id", "turn_id", "step", "rule_triggered",
        "entity_type", "entity_subtype", "original_type_desc",
        "span_id", "start", "end", "score", "token_applied",
        "conflict_resolved", "diarization_available", "usability_tag",
        "detector_id", "policy_version", "pipeline_version", "timestamp",
    )
    assert AUDIT_FIELDNAMES == expected


@pytest.mark.unit
def test_event_as_dict_unwraps_enums() -> None:
    row = event_as_dict(_make_event())
    assert row["entity_type"] == "TW_PHONE"  # not EntityType.TW_PHONE
    assert row["usability_tag"] == "USABLE"
    assert row["score"] == 0.95
    assert row["conflict_resolved"] is False


@pytest.mark.unit
def test_event_as_dict_covers_all_fields() -> None:
    row = event_as_dict(_make_event())
    assert set(row.keys()) == set(AUDIT_FIELDNAMES)

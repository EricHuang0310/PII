"""Tests for audit sinks (CSV, JSONL, Null)."""
from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from pii_masker.audit.event import AuditEvent
from pii_masker.audit.schema import AUDIT_FIELDNAMES
from pii_masker.audit.sinks.csv_sink import CsvAuditSink
from pii_masker.audit.sinks.jsonl_sink import JsonlAuditSink
from pii_masker.audit.sinks.null_sink import NullAuditSink
from pii_masker.domain.entity_type import EntityType
from pii_masker.usability.tags import UsabilityTag


def _event(i: int = 0) -> AuditEvent:
    return AuditEvent(
        session_id=f"S00{i}",
        trace_id="trace",
        turn_id="turn",
        step="Step1-5",
        rule_triggered="TW_PHONE",
        entity_type=EntityType.TW_PHONE,
        entity_subtype="MOBILE",
        original_type_desc="手機號碼",
        span_id=f"span-{i}",
        start=0,
        end=10,
        score=0.9,
        token_applied="[PHONE]",
        conflict_resolved=False,
        diarization_available=True,
        usability_tag=UsabilityTag.USABLE,
        detector_id="regex:tw_phone:v1",
        policy_version="v4.1.0",
        pipeline_version="2.0.0",
    )


# ── Null sink ───────────────────────────────────────────────────
@pytest.mark.unit
def test_null_sink_counts_events() -> None:
    sink = NullAuditSink()
    sink.write(_event(0))
    sink.write(_event(1))
    assert sink.events_written == 2
    sink.close()


# ── JSONL sink ──────────────────────────────────────────────────
@pytest.mark.unit
def test_jsonl_sink_writes_one_line_per_event(tmp_path: Path) -> None:
    path = tmp_path / "audit.jsonl"
    with JsonlAuditSink(path) as sink:
        sink.write(_event(0))
        sink.write(_event(1))

    lines = path.read_text(encoding="utf-8").strip().split("\n")
    assert len(lines) == 2
    row0 = json.loads(lines[0])
    assert row0["session_id"] == "S000"
    assert row0["entity_type"] == "TW_PHONE"


@pytest.mark.unit
def test_jsonl_sink_appends_when_enabled(tmp_path: Path) -> None:
    path = tmp_path / "audit.jsonl"
    with JsonlAuditSink(path) as s1:
        s1.write(_event(0))
    with JsonlAuditSink(path, append=True) as s2:
        s2.write(_event(1))
    lines = path.read_text(encoding="utf-8").strip().split("\n")
    assert len(lines) == 2


# ── CSV sink ────────────────────────────────────────────────────
@pytest.mark.unit
def test_csv_sink_writes_header_then_rows(tmp_path: Path) -> None:
    path = tmp_path / "audit.csv"
    with CsvAuditSink(path) as sink:
        sink.write(_event(0))
        sink.write(_event(1))

    with path.open(encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 2
    assert rows[0]["session_id"] == "S000"
    # All AUDIT_FIELDNAMES present as columns
    assert set(rows[0].keys()) == set(AUDIT_FIELDNAMES)


@pytest.mark.unit
def test_csv_sink_append_does_not_duplicate_header(tmp_path: Path) -> None:
    path = tmp_path / "audit.csv"
    with CsvAuditSink(path) as s1:
        s1.write(_event(0))
    with CsvAuditSink(path, append=True) as s2:
        s2.write(_event(1))

    content = path.read_text(encoding="utf-8")
    # Header appears exactly once
    header_line = ",".join(AUDIT_FIELDNAMES)
    assert content.count(header_line) == 1
    assert "S000" in content
    assert "S001" in content


@pytest.mark.unit
def test_csv_sink_write_many(tmp_path: Path) -> None:
    path = tmp_path / "audit.csv"
    with CsvAuditSink(path) as sink:
        sink.write_many([_event(0), _event(1), _event(2)])
    with path.open(encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 3

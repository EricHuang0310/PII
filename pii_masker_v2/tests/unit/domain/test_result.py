"""Tests for MaskingResult and ConflictEntry."""
from __future__ import annotations

import pytest

from pii_masker.domain.detection import Detection
from pii_masker.domain.entity_type import EntityType
from pii_masker.domain.result import ConflictEntry, MaskingResult
from pii_masker.domain.span import Span
from pii_masker.usability.tags import UsabilityTag


def _det(span: Span, entity_type: EntityType = EntityType.PERSON) -> Detection:
    return Detection(
        span=span,
        entity_type=entity_type,
        confidence=0.9,
        detector_id="regex:test:v1",
    )


def _build_result(**overrides: object) -> MaskingResult:
    d1 = _det(Span(0, 3))
    d2 = _det(Span(5, 8), EntityType.TW_PHONE)
    defaults = dict(
        session_id="S001",
        turn_id="T01",
        original_text="original",
        normalized_text="original",
        masked_text="[NAME]...[PHONE]",
        detections=[d1, d2],
        tokens={d1.span_id: "[NAME]", d2.span_id: "[PHONE]"},
        pseudonym_map={EntityType.PERSON: {"王小明": "[NAME]"}},
        conflict_log=[],
        usability_tag=UsabilityTag.USABLE,
        fallback_mode=False,
        diarization_available=True,
        policy_version="v4.1.0",
        pipeline_version="2.0.0",
    )
    defaults.update(overrides)
    return MaskingResult.build(**defaults)  # type: ignore[arg-type]


@pytest.mark.unit
def test_result_build_converts_to_immutable() -> None:
    r = _build_result()
    # tuples, not lists
    assert isinstance(r.detections, tuple)
    assert isinstance(r.conflict_log, tuple)


@pytest.mark.unit
def test_result_pseudonym_map_is_read_only() -> None:
    r = _build_result()
    with pytest.raises(TypeError):
        # MappingProxyType rejects item assignment
        r.pseudonym_map[EntityType.PERSON] = {"x": "y"}  # type: ignore[index]


@pytest.mark.unit
def test_result_tokens_is_read_only() -> None:
    r = _build_result()
    with pytest.raises(TypeError):
        r.tokens["anything"] = "[OOPS]"  # type: ignore[index]


@pytest.mark.unit
def test_result_is_frozen() -> None:
    r = _build_result()
    with pytest.raises(Exception):
        r.session_id = "changed"  # type: ignore[misc]


@pytest.mark.unit
def test_result_entity_count_and_types() -> None:
    r = _build_result()
    assert r.entity_count == 2
    assert r.entity_types == frozenset({EntityType.PERSON, EntityType.TW_PHONE})


@pytest.mark.unit
def test_conflict_entry_fields() -> None:
    winner = _det(Span(0, 10))
    loser = _det(Span(2, 6))
    entry = ConflictEntry(winner=winner, loser=loser, reason="CONTAINS:longer_wins")
    assert entry.winner.span.length == 10
    assert entry.loser.span.length == 4
    assert "CONTAINS" in entry.reason

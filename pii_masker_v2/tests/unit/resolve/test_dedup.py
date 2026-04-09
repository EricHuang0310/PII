"""Tests for exact-duplicate dedup (Step 0)."""
from __future__ import annotations

import pytest

from pii_masker.domain.detection import Detection
from pii_masker.domain.entity_type import EntityType
from pii_masker.domain.span import Span
from pii_masker.resolve.dedup import dedup_exact


def _det(start: int, end: int, et: EntityType, score: float) -> Detection:
    return Detection(
        span=Span(start, end),
        entity_type=et,
        confidence=score,
        detector_id=f"regex:{et.value.lower()}:v-test",
    )


@pytest.mark.unit
def test_dedup_empty() -> None:
    out, log = dedup_exact([])
    assert out == []
    assert log == []


@pytest.mark.unit
def test_dedup_no_duplicates_passthrough() -> None:
    dets = [
        _det(0, 5, EntityType.PERSON, 0.9),
        _det(10, 15, EntityType.TW_PHONE, 0.85),
    ]
    out, log = dedup_exact(dets)
    assert out == dets
    assert log == []


@pytest.mark.unit
def test_dedup_higher_score_wins() -> None:
    a = _det(0, 5, EntityType.PERSON, 0.8)
    b = _det(0, 5, EntityType.PERSON, 0.95)  # same span + type, higher score
    out, log = dedup_exact([a, b])
    assert len(out) == 1
    assert out[0].confidence == 0.95
    assert len(log) == 1
    assert log[0].winner is b
    assert log[0].loser is a
    assert "higher_score_wins" in log[0].reason


@pytest.mark.unit
def test_dedup_tie_keeps_first() -> None:
    a = _det(0, 5, EntityType.PERSON, 0.8)
    b = _det(0, 5, EntityType.PERSON, 0.8)
    out, log = dedup_exact([a, b])
    assert len(out) == 1
    assert out[0] is a
    assert log[0].winner is a
    assert log[0].loser is b
    assert "first_wins" in log[0].reason


@pytest.mark.unit
def test_dedup_different_entity_type_not_deduped() -> None:
    """Same span but different entity type is NOT a duplicate — goes to later layers."""
    a = _det(0, 5, EntityType.PERSON, 0.8)
    b = _det(0, 5, EntityType.LOCATION, 0.85)
    out, log = dedup_exact([a, b])
    assert len(out) == 2
    assert log == []


@pytest.mark.unit
def test_dedup_preserves_order() -> None:
    """The first-occurrence order of survivors must be stable."""
    a = _det(0, 5, EntityType.PERSON, 0.9)
    b = _det(10, 15, EntityType.TW_PHONE, 0.8)
    c = _det(0, 5, EntityType.PERSON, 0.7)  # dup of a, worse score
    out, _ = dedup_exact([a, b, c])
    assert out == [a, b]

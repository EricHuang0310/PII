"""Tests for Detection — especially the immutable boosted() contract."""
from __future__ import annotations

import pytest

from pii_masker.domain.detection import Detection
from pii_masker.domain.entity_type import EntityType
from pii_masker.domain.span import Span


def _make(confidence: float = 0.8) -> Detection:
    return Detection(
        span=Span(0, 5),
        entity_type=EntityType.PERSON,
        confidence=confidence,
        detector_id="regex:test:v1",
    )


@pytest.mark.unit
def test_detection_span_id_auto_populated_and_unique() -> None:
    a = _make()
    b = _make()
    assert a.span_id
    assert b.span_id
    assert a.span_id != b.span_id  # UUIDs


@pytest.mark.unit
def test_detection_span_id_stable_across_access() -> None:
    d = _make()
    assert d.span_id == d.span_id  # same value on re-access


@pytest.mark.unit
def test_detection_rejects_out_of_range_confidence() -> None:
    with pytest.raises(ValueError, match=r"must be in \[0, 1\]"):
        _make(confidence=1.5)
    with pytest.raises(ValueError, match=r"must be in \[0, 1\]"):
        _make(confidence=-0.1)


@pytest.mark.unit
def test_detection_rejects_empty_detector_id() -> None:
    with pytest.raises(ValueError, match="detector_id must be non-empty"):
        Detection(
            span=Span(0, 5),
            entity_type=EntityType.PERSON,
            confidence=0.8,
            detector_id="",
        )


@pytest.mark.unit
def test_detection_boosted_returns_new_instance() -> None:
    """CRITICAL invariant: boosted() must NOT mutate the input.

    This is the v2 fix for v3/v4's `r.score = min(1.0, r.score + 0.15)`.
    """
    original = _make(confidence=0.5)
    boosted = original.boosted(0.2)
    assert boosted is not original
    assert original.confidence == 0.5  # input unchanged
    assert boosted.confidence == pytest.approx(0.7)
    assert boosted.span_id == original.span_id  # same audit join key


@pytest.mark.unit
def test_detection_boosted_clamps_to_upper_bound() -> None:
    assert _make(0.9).boosted(0.5).confidence == 1.0


@pytest.mark.unit
def test_detection_boosted_clamps_to_lower_bound() -> None:
    """Negative delta should clamp at 0, not go negative."""
    assert _make(0.1).boosted(-0.5).confidence == 0.0


@pytest.mark.unit
def test_detection_is_frozen() -> None:
    d = _make()
    with pytest.raises(Exception):
        d.confidence = 0.99  # type: ignore[misc]


@pytest.mark.unit
def test_detection_to_dict_roundtrip_keys() -> None:
    d = _make()
    out = d.to_dict()
    assert out["span_id"] == d.span_id
    assert out["start"] == 0
    assert out["end"] == 5
    assert out["entity_type"] == "PERSON"
    assert out["confidence"] == pytest.approx(0.8)
    assert out["detector_id"] == "regex:test:v1"


@pytest.mark.unit
def test_detection_with_raw_text_returns_new_instance() -> None:
    d = _make()
    with_text = d.with_raw_text("王小明")
    assert with_text is not d
    assert d.raw_text == ""
    assert with_text.raw_text == "王小明"
    assert with_text.span_id == d.span_id

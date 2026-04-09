"""Tests for per-span replacement."""
from __future__ import annotations

import pytest

from pii_masker.domain.detection import Detection
from pii_masker.domain.entity_type import EntityType
from pii_masker.domain.span import Span
from pii_masker.tokenize.replacer import replace


def _det(start: int, end: int, et: EntityType = EntityType.PERSON) -> Detection:
    return Detection(
        span=Span(start, end),
        entity_type=et,
        confidence=0.9,
        detector_id="regex:test:v1",
    )


@pytest.mark.unit
def test_replace_single_span() -> None:
    d = _det(3, 6)
    out = replace("abcDEFghi", [d], {d.span_id: "[X]"})
    assert out == "abc[X]ghi"


@pytest.mark.unit
def test_replace_multiple_same_type_preserves_each() -> None:
    """Critical Bug 1 invariant: same-type multi-span must not overwrite.

    v3/v4 originally used Presidio's anonymize() with entity-type-keyed
    operators which overwrote all PERSON spans with one value. The per-span
    approach replaces each independently.
    """
    a = _det(0, 3)
    b = _det(6, 9)
    out = replace(
        "ABCdefDEFghi",
        [a, b],
        {a.span_id: "[A]", b.span_id: "[B]"},
    )
    assert out == "[A]def[B]ghi"


@pytest.mark.unit
def test_replace_reverse_order_insensitive() -> None:
    """Reversed input order produces the same output — sort is internal."""
    a = _det(0, 3)
    b = _det(6, 9)
    tokens = {a.span_id: "[A]", b.span_id: "[B]"}
    out_forward = replace("ABCdefDEF", [a, b], tokens)
    out_reverse = replace("ABCdefDEF", [b, a], tokens)
    assert out_forward == out_reverse == "[A]def[B]"


@pytest.mark.unit
def test_replace_skips_missing_token() -> None:
    d = _det(0, 3)
    out = replace("ABCdef", [d], {})  # empty token map
    assert out == "ABCdef"  # unchanged


@pytest.mark.unit
def test_replace_empty_detections_returns_text_unchanged() -> None:
    assert replace("hello", [], {}) == "hello"


@pytest.mark.unit
def test_replace_different_token_lengths() -> None:
    """Token lengths can differ from span lengths — reverse sort handles this."""
    a = _det(0, 3)
    b = _det(6, 9)
    out = replace(
        "ABCdefDEF",
        [a, b],
        {a.span_id: "[LONG_TOKEN]", b.span_id: "[X]"},
    )
    assert out == "[LONG_TOKEN]def[X]"

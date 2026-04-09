"""Tests for Span."""
from __future__ import annotations

import pytest

from pii_masker.domain.span import Span


@pytest.mark.unit
def test_span_length() -> None:
    assert Span(0, 5).length == 5
    assert Span(3, 3).length == 0


@pytest.mark.unit
def test_span_rejects_negative_start() -> None:
    with pytest.raises(ValueError, match="start must be >= 0"):
        Span(-1, 5)


@pytest.mark.unit
def test_span_rejects_end_before_start() -> None:
    with pytest.raises(ValueError, match="must be >= start"):
        Span(5, 3)


@pytest.mark.unit
def test_span_overlaps_true() -> None:
    a = Span(0, 5)
    b = Span(3, 8)
    assert a.overlaps(b)
    assert b.overlaps(a)


@pytest.mark.unit
def test_span_overlaps_false_when_touching() -> None:
    """Touching spans do NOT overlap — [0, 5) and [5, 10) share no chars."""
    a = Span(0, 5)
    b = Span(5, 10)
    assert not a.overlaps(b)
    assert not b.overlaps(a)


@pytest.mark.unit
def test_span_overlaps_false_when_disjoint() -> None:
    assert not Span(0, 3).overlaps(Span(5, 9))


@pytest.mark.unit
def test_span_contains_strict() -> None:
    """contains() is STRICT: equal-length spans do not count as containment.

    This matches v3/v4 conflict_resolver._contains.
    """
    outer = Span(0, 10)
    inner = Span(2, 5)
    assert outer.contains(inner)
    assert not inner.contains(outer)


@pytest.mark.unit
def test_span_contains_false_for_equal_length() -> None:
    a = Span(0, 5)
    b = Span(0, 5)
    assert not a.contains(b)
    assert not b.contains(a)


@pytest.mark.unit
def test_span_is_hashable_and_frozen() -> None:
    a = Span(1, 2)
    # frozen → hashable → can be a dict key
    d = {a: "yes"}
    assert d[Span(1, 2)] == "yes"
    # frozen → cannot mutate
    with pytest.raises(Exception):
        a.start = 99  # type: ignore[misc]

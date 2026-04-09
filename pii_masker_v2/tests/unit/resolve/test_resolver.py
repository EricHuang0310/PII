"""Tests for the full conflict resolver composition."""
from __future__ import annotations

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from pii_masker.domain.detection import Detection
from pii_masker.domain.entity_type import EntityType
from pii_masker.domain.span import Span
from pii_masker.resolve import resolver


def _det(start: int, end: int, et: EntityType, score: float = 0.8) -> Detection:
    return Detection(
        span=Span(start, end),
        entity_type=et,
        confidence=score,
        detector_id=f"regex:{et.value.lower()}:v-test",
    )


@pytest.mark.unit
def test_resolver_empty(default_policy) -> None:  # type: ignore[no-untyped-def]
    kept, log = resolver.resolve([], default_policy)
    assert kept == []
    assert log == []


@pytest.mark.unit
def test_resolver_passthrough_no_overlap(default_policy) -> None:  # type: ignore[no-untyped-def]
    dets = [
        _det(0, 5, EntityType.PERSON),
        _det(10, 20, EntityType.TW_PHONE),
        _det(25, 35, EntityType.TW_CREDIT_CARD),
    ]
    kept, log = resolver.resolve(dets, default_policy)
    assert len(kept) == 3
    assert log == []


@pytest.mark.unit
def test_resolver_contains_longer_wins(default_policy) -> None:  # type: ignore[no-untyped-def]
    """Longer span strictly containing a shorter span → longer wins."""
    outer = _det(0, 20, EntityType.LOCATION, 0.8)
    inner = _det(5, 10, EntityType.LOCATION, 0.8)
    kept, log = resolver.resolve([outer, inner], default_policy)
    assert len(kept) == 1
    assert kept[0] is outer
    assert "CONTAINS" in log[0].reason


@pytest.mark.unit
def test_resolver_risk_level_wins(default_policy) -> None:  # type: ignore[no-untyped-def]
    """Partial overlap, same length: higher risk entity wins.

    TW_CREDIT_CARD has risk 5; LOCATION has risk 3. Both 10 chars long, partial overlap.
    """
    card = _det(0, 10, EntityType.TW_CREDIT_CARD, 0.9)
    loc = _det(5, 15, EntityType.LOCATION, 0.9)
    kept, log = resolver.resolve([card, loc], default_policy)
    assert len(kept) == 1
    assert kept[0].entity_type is EntityType.TW_CREDIT_CARD
    assert "RISK_LEVEL" in log[0].reason


@pytest.mark.unit
def test_resolver_exact_duplicate_deduped(default_policy) -> None:  # type: ignore[no-untyped-def]
    """Two detectors (CKIP + address) flag the same LOCATION span."""
    ckip = _det(0, 5, EntityType.LOCATION, 0.90)
    addr = _det(0, 5, EntityType.LOCATION, 0.85)
    kept, log = resolver.resolve([ckip, addr], default_policy)
    assert len(kept) == 1
    assert kept[0].confidence == 0.90
    assert any("EXACT_DUP" in e.reason for e in log)


@pytest.mark.unit
def test_resolver_no_overlap_in_output_determinism(default_policy) -> None:  # type: ignore[no-untyped-def]
    """Resolver output must never contain two overlapping detections."""
    dets = [
        _det(0, 10, EntityType.LOCATION, 0.9),
        _det(5, 15, EntityType.PERSON, 0.9),
        _det(12, 20, EntityType.TW_PHONE, 0.9),
    ]
    kept, _ = resolver.resolve(dets, default_policy)
    for i, a in enumerate(kept):
        for b in kept[i + 1 :]:
            assert not a.span.overlaps(
                b.span
            ), f"{a.entity_type} and {b.entity_type} overlap"


@pytest.mark.unit
def test_resolver_preserves_all_conflict_log_entries_by_identity(
    default_policy,  # type: ignore[no-untyped-def]
) -> None:
    """Conflict log entries store Detection objects (not entity_type strings).

    This is the v3/v4 Bug 2/3 invariant — audit uses id() to track winners.
    """
    a = _det(0, 10, EntityType.LOCATION, 0.9)
    b = _det(5, 8, EntityType.LOCATION, 0.9)
    _, log = resolver.resolve([a, b], default_policy)
    assert len(log) == 1
    assert log[0].winner is a
    assert log[0].loser is b


# ── Property tests ──────────────────────────────────────────────
def _random_detection(start: int, length: int, et_name: str) -> Detection:
    return Detection(
        span=Span(start, start + length),
        entity_type=EntityType(et_name),
        confidence=0.85,
        detector_id=f"regex:{et_name.lower()}:v-test",
    )


@pytest.mark.property
@settings(
    max_examples=200,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
@given(
    st.lists(
        st.tuples(
            st.integers(min_value=0, max_value=50),
            st.integers(min_value=1, max_value=20),
            st.sampled_from([e.value for e in EntityType]),
        ),
        min_size=0,
        max_size=15,
    )
)
def test_resolver_output_has_no_overlapping_spans(
    default_policy,  # type: ignore[no-untyped-def]
    raw: list[tuple[int, int, str]],
) -> None:
    """For any valid input, the resolver output has zero overlapping pairs."""
    dets = [_random_detection(s, l, e) for s, l, e in raw]
    kept, _ = resolver.resolve(dets, default_policy)
    for i, a in enumerate(kept):
        for b in kept[i + 1 :]:
            assert not a.span.overlaps(b.span), (
                f"overlap in resolver output: {a.entity_type}[{a.span}] vs "
                f"{b.entity_type}[{b.span}]"
            )

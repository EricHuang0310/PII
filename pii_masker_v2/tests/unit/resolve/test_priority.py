"""Tests for composite priority scoring."""
from __future__ import annotations

import pytest

from pii_masker.domain.detection import Detection
from pii_masker.domain.entity_type import EntityType
from pii_masker.domain.span import Span
from pii_masker.resolve.priority import compute_score, has_keyword_context


def _det(et: EntityType, score: float) -> Detection:
    return Detection(
        span=Span(0, 5),
        entity_type=et,
        confidence=score,
        detector_id="regex:test:v1",
    )


@pytest.mark.unit
def test_has_keyword_context_high_score() -> None:
    assert has_keyword_context(_det(EntityType.PERSON, 0.95)) is True


@pytest.mark.unit
def test_has_keyword_context_low_score() -> None:
    assert has_keyword_context(_det(EntityType.PERSON, 0.5)) is False


@pytest.mark.unit
def test_compute_score_uses_policy_priority(default_policy) -> None:  # type: ignore[no-untyped-def]
    """Higher-priority entity types should produce higher composite scores."""
    person = _det(EntityType.PERSON, 0.8)       # priority 95, risk 4
    campaign = _det(EntityType.CAMPAIGN, 0.8)    # priority 30, risk 1
    assert compute_score(person, default_policy) > compute_score(campaign, default_policy)


@pytest.mark.unit
def test_compute_score_includes_risk_component(default_policy) -> None:  # type: ignore[no-untyped-def]
    """Credit card (risk 5) should beat address (risk 3) at same confidence."""
    card = _det(EntityType.TW_CREDIT_CARD, 0.5)  # priority 100, risk 5
    addr = _det(EntityType.LOCATION, 0.5)         # priority 78, risk 3
    assert compute_score(card, default_policy) > compute_score(addr, default_policy)

"""Tests for the conditional AMOUNT masking rule."""
from __future__ import annotations

import pytest

from pii_masker.domain.detection import Detection
from pii_masker.domain.entity_type import EntityType
from pii_masker.domain.policy import ConditionalAmountPolicy
from pii_masker.domain.span import Span
from pii_masker.rules import conditional_amount


def _det(start: int, end: int, et: EntityType) -> Detection:
    return Detection(
        span=Span(start, end),
        entity_type=et,
        confidence=0.8,
        detector_id="regex:test:v1",
    )


@pytest.fixture
def policy() -> ConditionalAmountPolicy:
    return ConditionalAmountPolicy(
        trigger_entities=frozenset({EntityType.TW_BANK_ACCOUNT, EntityType.TW_CREDIT_CARD}),
        proximity_chars=60,
    )


@pytest.mark.unit
def test_amount_dropped_when_no_triggers(policy: ConditionalAmountPolicy) -> None:
    dets = [_det(0, 5, EntityType.AMOUNT)]
    out = conditional_amount.apply(dets, policy)
    assert out == []


@pytest.mark.unit
def test_amount_kept_near_account(policy: ConditionalAmountPolicy) -> None:
    amount = _det(0, 5, EntityType.AMOUNT)
    account = _det(10, 20, EntityType.TW_BANK_ACCOUNT)
    out = conditional_amount.apply([amount, account], policy)
    assert len(out) == 2


@pytest.mark.unit
def test_amount_dropped_when_far_from_account(policy: ConditionalAmountPolicy) -> None:
    amount = _det(0, 5, EntityType.AMOUNT)
    account = _det(200, 210, EntityType.TW_BANK_ACCOUNT)
    out = conditional_amount.apply([amount, account], policy)
    # amount was dropped; account kept
    assert len(out) == 1
    assert out[0].entity_type is EntityType.TW_BANK_ACCOUNT


@pytest.mark.unit
def test_amount_kept_near_credit_card(policy: ConditionalAmountPolicy) -> None:
    amount = _det(0, 5, EntityType.AMOUNT)
    card = _det(10, 26, EntityType.TW_CREDIT_CARD)
    out = conditional_amount.apply([amount, card], policy)
    assert len(out) == 2


@pytest.mark.unit
def test_amount_txn_never_filtered(policy: ConditionalAmountPolicy) -> None:
    """AMOUNT_TXN is unaffected — it's always kept."""
    txn_amount = _det(0, 5, EntityType.AMOUNT_TXN)
    out = conditional_amount.apply([txn_amount], policy)
    assert out == [txn_amount]


@pytest.mark.unit
def test_rule_does_not_mutate_input(policy: ConditionalAmountPolicy) -> None:
    dets = [_det(0, 5, EntityType.AMOUNT), _det(10, 20, EntityType.TW_BANK_ACCOUNT)]
    original_ids = [id(d) for d in dets]
    conditional_amount.apply(dets, policy)
    assert [id(d) for d in dets] == original_ids

"""Tests for MaskingPolicy validation."""
from __future__ import annotations

import re

import pytest

from pii_masker.domain.entity_type import EntityType
from pii_masker.domain.policy import (
    AddressPolicy,
    ConditionalAmountPolicy,
    DiarizationFallbackPolicy,
    MaskingPolicy,
    UsabilityPolicy,
)


def _make_policy(**overrides: object) -> MaskingPolicy:
    defaults: dict[str, object] = dict(
        version="v-test",
        schema_version=1,
        score_threshold=0.6,
        mask_branch_code=False,
        conditional_amount=ConditionalAmountPolicy(
            trigger_entities=frozenset({EntityType.TW_BANK_ACCOUNT}),
            proximity_chars=60,
        ),
        high_risk_txn_verbs=("轉帳", "匯款"),
        diarization_fallback=DiarizationFallbackPolicy(
            answer_window_chars=30,
            question_boost=0.15,
            answer_boost=0.10,
            diarization_threshold=0.8,
            agent_question_patterns=(re.compile(r"請問"),),
            answer_patterns=(re.compile(r"是\s*\d+"),),
        ),
        address=AddressPolicy(
            admin_districts=("台北市",),
            chain_landmarks=("Costco",),
        ),
        usability=UsabilityPolicy(
            degraded_masking_threshold=3.0,
            asr_confidence_threshold=0.7,
        ),
        entity_priority={EntityType.PERSON: 95, EntityType.TW_CREDIT_CARD: 100},
        entity_risk_level={EntityType.PERSON: 4, EntityType.TW_CREDIT_CARD: 5},
        pseudonym_entities=frozenset({EntityType.PERSON, EntityType.TW_CREDIT_CARD}),
        token_map={
            EntityType.PERSON: "[NAME]",
            EntityType.TW_CREDIT_CARD: "[CARD]",
        },
    )
    defaults.update(overrides)
    return MaskingPolicy(**defaults)  # type: ignore[arg-type]


@pytest.mark.unit
def test_policy_happy_path() -> None:
    p = _make_policy()
    assert p.version == "v-test"
    assert p.priority_of(EntityType.PERSON) == 95
    assert p.risk_of(EntityType.TW_CREDIT_CARD) == 5
    assert p.token_for(EntityType.PERSON) == "[NAME]"
    assert p.is_pseudonym_entity(EntityType.PERSON) is True
    assert p.is_pseudonym_entity(EntityType.OTP) is False


@pytest.mark.unit
def test_policy_rejects_out_of_range_score_threshold() -> None:
    with pytest.raises(ValueError, match=r"score_threshold must be in \[0, 1\]"):
        _make_policy(score_threshold=1.5)


@pytest.mark.unit
def test_policy_rejects_pseudonym_entity_missing_from_priority() -> None:
    with pytest.raises(ValueError, match="missing from entity_priority"):
        _make_policy(
            pseudonym_entities=frozenset({EntityType.PERSON, EntityType.ORG}),
        )


@pytest.mark.unit
def test_policy_rejects_priority_entity_missing_from_token_map() -> None:
    with pytest.raises(ValueError, match="missing from token_map"):
        _make_policy(
            entity_priority={EntityType.PERSON: 95, EntityType.ORG: 76},
            entity_risk_level={EntityType.PERSON: 4, EntityType.ORG: 2},
            pseudonym_entities=frozenset({EntityType.PERSON}),
            token_map={EntityType.PERSON: "[NAME]"},  # missing ORG
        )


@pytest.mark.unit
def test_policy_token_for_unknown_entity_returns_fallback() -> None:
    p = _make_policy()
    # OTP not in this mini policy — falls back to generic token
    assert p.token_for(EntityType.OTP) == "[OTP]"


@pytest.mark.unit
def test_conditional_amount_rejects_negative_proximity() -> None:
    with pytest.raises(ValueError, match="proximity_chars must be >= 0"):
        ConditionalAmountPolicy(
            trigger_entities=frozenset({EntityType.TW_BANK_ACCOUNT}),
            proximity_chars=-1,
        )


@pytest.mark.unit
def test_diarization_fallback_rejects_out_of_range_boost() -> None:
    with pytest.raises(ValueError, match=r"question_boost must be in \[0, 1\]"):
        DiarizationFallbackPolicy(
            answer_window_chars=10,
            question_boost=2.0,
            answer_boost=0.1,
            diarization_threshold=0.8,
            agent_question_patterns=(),
            answer_patterns=(),
        )


@pytest.mark.unit
def test_usability_rejects_negative_degraded_threshold() -> None:
    with pytest.raises(ValueError, match="degraded_masking_threshold must be >= 0"):
        UsabilityPolicy(
            degraded_masking_threshold=-0.1,
            asr_confidence_threshold=0.7,
        )

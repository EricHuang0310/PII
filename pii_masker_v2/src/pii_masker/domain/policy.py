"""MaskingPolicy — frozen, validated business rules loaded from policy/defaults.yaml.

All tunables that lived in v3/v4's `config.py` live here as typed dataclass
fields. The policy is built ONCE at startup by `config.loader.load_policy`,
validated, and then passed by reference through the pipeline.

Immutability: every field is a frozen dataclass, tuple, or frozenset. There is
no way to mutate a policy after construction. If you need a different policy at
runtime (e.g. a test override), build a new one.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Pattern

from pii_masker.domain.entity_type import EntityType


@dataclass(frozen=True, slots=True)
class ConditionalAmountPolicy:
    """AMOUNT is only masked when it's near a trigger entity (account/card)."""

    trigger_entities: frozenset[EntityType]
    proximity_chars: int

    def __post_init__(self) -> None:
        if self.proximity_chars < 0:
            raise ValueError(
                f"ConditionalAmountPolicy.proximity_chars must be >= 0, "
                f"got {self.proximity_chars}"
            )


@dataclass(frozen=True, slots=True)
class DiarizationFallbackPolicy:
    """Fallback scoring when diarization is unavailable."""

    answer_window_chars: int
    question_boost: float
    answer_boost: float
    diarization_threshold: float
    agent_question_patterns: tuple[Pattern[str], ...]
    answer_patterns: tuple[Pattern[str], ...]

    def __post_init__(self) -> None:
        if self.answer_window_chars < 0:
            raise ValueError("answer_window_chars must be >= 0")
        if not 0.0 <= self.question_boost <= 1.0:
            raise ValueError("question_boost must be in [0, 1]")
        if not 0.0 <= self.answer_boost <= 1.0:
            raise ValueError("answer_boost must be in [0, 1]")
        if not 0.0 <= self.diarization_threshold <= 1.0:
            raise ValueError("diarization_threshold must be in [0, 1]")


@dataclass(frozen=True, slots=True)
class AddressPolicy:
    """Dictionary data for the three-layer address detector."""

    admin_districts: tuple[str, ...]
    chain_landmarks: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class UsabilityPolicy:
    """Usability tagging thresholds."""

    degraded_masking_threshold: float  # entities per 100 chars
    asr_confidence_threshold: float

    def __post_init__(self) -> None:
        if self.degraded_masking_threshold < 0:
            raise ValueError("degraded_masking_threshold must be >= 0")
        if not 0.0 <= self.asr_confidence_threshold <= 1.0:
            raise ValueError("asr_confidence_threshold must be in [0, 1]")


@dataclass(frozen=True, slots=True)
class MaskingPolicy:
    """Top-level frozen policy. Loaded once, passed everywhere by reference."""

    version: str
    schema_version: int
    score_threshold: float
    mask_branch_code: bool

    conditional_amount: ConditionalAmountPolicy
    high_risk_txn_verbs: tuple[str, ...]
    diarization_fallback: DiarizationFallbackPolicy
    address: AddressPolicy
    usability: UsabilityPolicy

    entity_priority: dict[EntityType, int]
    entity_risk_level: dict[EntityType, int]
    pseudonym_entities: frozenset[EntityType]
    token_map: dict[EntityType, str]

    strict_validation: bool = True  # enables Luhn + TW-ID checksum in detectors

    def __post_init__(self) -> None:
        if not 0.0 <= self.score_threshold <= 1.0:
            raise ValueError(
                f"MaskingPolicy.score_threshold must be in [0, 1], "
                f"got {self.score_threshold}"
            )
        if self.schema_version < 1:
            raise ValueError(
                f"MaskingPolicy.schema_version must be >= 1, got {self.schema_version}"
            )
        # Every pseudonym entity must also have a priority — otherwise the
        # conflict resolver will score it as 0 and drop it in overlap cases.
        missing_priority = self.pseudonym_entities - set(self.entity_priority.keys())
        if missing_priority:
            raise ValueError(
                f"pseudonym_entities {sorted(e.value for e in missing_priority)} "
                f"are missing from entity_priority"
            )
        # Token map must cover every priority entity — otherwise masking will
        # fall back to the generic `[TYPE]` token, which is almost certainly
        # a config bug.
        missing_tokens = set(self.entity_priority.keys()) - set(self.token_map.keys())
        if missing_tokens:
            raise ValueError(
                f"entity_priority types {sorted(e.value for e in missing_tokens)} "
                f"are missing from token_map"
            )

    def priority_of(self, entity_type: EntityType) -> int:
        return self.entity_priority.get(entity_type, 0)

    def risk_of(self, entity_type: EntityType) -> int:
        return self.entity_risk_level.get(entity_type, 0)

    def token_for(self, entity_type: EntityType) -> str:
        return self.token_map.get(entity_type, f"[{entity_type.value}]")

    def is_pseudonym_entity(self, entity_type: EntityType) -> bool:
        return entity_type in self.pseudonym_entities

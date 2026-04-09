"""MaskingResult — the immutable output of one `mask()` call.

All collections are immutable (`tuple`, `Mapping` at the type level). Nothing
downstream can mutate a result after it is returned — this guarantees that the
audit log, pseudonym map, and leak scan status stay consistent with what the
pipeline actually produced.
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType

from pii_masker.domain.detection import Detection
from pii_masker.domain.entity_type import EntityType
from pii_masker.usability.tags import UsabilityTag


@dataclass(frozen=True, slots=True)
class ConflictEntry:
    """One conflict resolver decision: winner, loser, and the reason.

    v3/v4 stored this as a raw tuple and the pipeline had to pattern-match on
    it. Here it's a typed frozen dataclass so consumers can name the fields and
    mypy catches mistakes.
    """

    winner: Detection
    loser: Detection
    reason: str


def _freeze_map(data: Mapping[EntityType, Mapping[str, str]]) -> Mapping[EntityType, Mapping[str, str]]:
    """Wrap a nested mapping in read-only MappingProxyType views."""
    return MappingProxyType({
        k: MappingProxyType(dict(v)) for k, v in data.items()
    })


def _freeze_token_map(data: Mapping[str, str]) -> Mapping[str, str]:
    return MappingProxyType(dict(data))


@dataclass(frozen=True, slots=True)
class MaskingResult:
    """Immutable output of one `mask()` call.

    Attributes:
        session_id: user-supplied session identifier
        turn_id: per-turn identifier (empty for single-text masking)
        original_text: the text as passed in
        normalized_text: after Step 0 normalization
        masked_text: the final text with PII replaced by tokens
        detections: frozen tuple of final detections (post-resolve)
        tokens: mapping from Detection.span_id -> token string (e.g. "[NAME]")
        pseudonym_map: entity_type -> {original_value -> token} for audit readback
        conflict_log: frozen tuple of conflict resolver decisions
        usability_tag: output of the usability tagger
        fallback_mode: True if diarization was unavailable and fallback ran
        diarization_available: True if the caller's diarization signal was usable
        policy_version: version string from MaskingPolicy.version
        pipeline_version: version string from the pii_masker package
        leak_scan_passed: True if Step 7 ran and found zero residual PII.
            A MaskingResult with leak_scan_passed=False is only ever produced
            when the caller explicitly disables leak scanning; the default
            pipeline path raises PIILeakError instead.
    """

    session_id: str
    turn_id: str
    original_text: str
    normalized_text: str
    masked_text: str
    detections: tuple[Detection, ...]
    tokens: Mapping[str, str]
    pseudonym_map: Mapping[EntityType, Mapping[str, str]]
    conflict_log: tuple[ConflictEntry, ...]
    usability_tag: UsabilityTag
    fallback_mode: bool
    diarization_available: bool
    policy_version: str
    pipeline_version: str
    leak_scan_passed: bool = True

    # Convenience factory to make construction safer — callers pass mutable
    # dicts/lists and get back a result with frozen views.
    @classmethod
    def build(
        cls,
        *,
        session_id: str,
        turn_id: str,
        original_text: str,
        normalized_text: str,
        masked_text: str,
        detections: tuple[Detection, ...] | list[Detection],
        tokens: Mapping[str, str],
        pseudonym_map: Mapping[EntityType, Mapping[str, str]],
        conflict_log: tuple[ConflictEntry, ...] | list[ConflictEntry],
        usability_tag: UsabilityTag,
        fallback_mode: bool,
        diarization_available: bool,
        policy_version: str,
        pipeline_version: str,
        leak_scan_passed: bool = True,
    ) -> MaskingResult:
        return cls(
            session_id=session_id,
            turn_id=turn_id,
            original_text=original_text,
            normalized_text=normalized_text,
            masked_text=masked_text,
            detections=tuple(detections),
            tokens=_freeze_token_map(tokens),
            pseudonym_map=_freeze_map(pseudonym_map),
            conflict_log=tuple(conflict_log),
            usability_tag=usability_tag,
            fallback_mode=fallback_mode,
            diarization_available=diarization_available,
            policy_version=policy_version,
            pipeline_version=pipeline_version,
            leak_scan_passed=leak_scan_passed,
        )

    @property
    def entity_count(self) -> int:
        return len(self.detections)

    @property
    def entity_types(self) -> frozenset[EntityType]:
        return frozenset(d.entity_type for d in self.detections)

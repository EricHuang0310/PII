"""Detection — a single entity detected by one detector, with a stable span_id.

The v3/v4 pipeline keys its `token_map` and `resolved_ids` on `id(RecognizerResult)`,
which is ephemeral and breaks if anything round-trips through serialization. We use
a stable UUID instead so detections can survive JSONL dumps, cross-process transport,
and distributed pipelines.

Immutability: `Detection` is frozen. To boost confidence (for the diarization fallback
and speaker-aware rule), use `.boosted(delta)` which returns a NEW detection. This is
the v2 contract that fixes the current `r.score += 0.15` mutation bug.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field, replace
from typing import Any

from pii_masker.domain.entity_type import EntityType
from pii_masker.domain.span import Span


def _new_span_id() -> str:
    """Generate a stable detection ID (UUID4, hex form, 32 chars)."""
    return uuid.uuid4().hex


@dataclass(frozen=True, slots=True)
class Detection:
    """One PII detection from one detector.

    Attributes:
        span: half-open character interval into the normalized text
        entity_type: closed-set PII type
        confidence: 0.0..1.0 calibrated confidence score
        detector_id: stable identifier of the producing detector, e.g.
            "regex:tw_phone:v1" or "ner:ckip:bert-base:v1". Used for audit and
            for debugging why a given span was detected.
        subtype: optional finer-grained label (MOBILE / LANDLINE / ADDR_L1 / ...)
        raw_text: the slice of normalized text covered by `span`. Stored for audit
            readability; never used for decision-making.
        span_id: stable UUID, generated at construction time unless explicitly set.
            Survives serialization. Use this as the audit join key, NOT id().
    """

    span: Span
    entity_type: EntityType
    confidence: float
    detector_id: str
    subtype: str | None = None
    raw_text: str = ""
    span_id: str = field(default_factory=_new_span_id)

    def __post_init__(self) -> None:
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError(
                f"Detection.confidence must be in [0, 1], got {self.confidence}"
            )
        if not self.detector_id:
            raise ValueError("Detection.detector_id must be non-empty")

    def boosted(self, delta: float) -> Detection:
        """Return a NEW detection with confidence clamped to [0, 1].

        This is the immutable replacement for the v3/v4
        `r.score = min(1.0, r.score + 0.15)` in `_apply_speaker_aware_masking`.
        It preserves the span_id so the audit trail still joins to the same event.
        """
        new_confidence = max(0.0, min(1.0, self.confidence + delta))
        return replace(self, confidence=new_confidence)

    def with_raw_text(self, raw: str) -> Detection:
        """Return a copy with the raw_text populated (used by the pipeline)."""
        return replace(self, raw_text=raw)

    def to_dict(self) -> dict[str, Any]:
        """Serializable form for audit sinks and JSONL dumps."""
        return {
            "span_id": self.span_id,
            "start": self.span.start,
            "end": self.span.end,
            "entity_type": self.entity_type.value,
            "confidence": self.confidence,
            "detector_id": self.detector_id,
            "subtype": self.subtype,
            "raw_text": self.raw_text,
        }

"""Usability tagging — compute a UsabilityTag from the masking result.

Ports v3/v4 `_compute_usability` with the Bug 4 fix baked in: branches on
`diarization_available` only, no redundant `in_fallback` parameter.

Priority order (first match wins):
    1. LOW_AUDIO_QUALITY  — asr_confidence < threshold
    2. FALLBACK_MODE      — no diarization, but agent-question pattern fired
    3. NO_DIARIZATION     — no diarization and no fallback signal
    4. DEGRADED_MASKING   — entity density > threshold (per 100 chars)
    5. USABLE             — default
"""
from __future__ import annotations

from collections.abc import Sequence
from typing import Pattern

from pii_masker.domain.detection import Detection
from pii_masker.domain.policy import DiarizationFallbackPolicy, UsabilityPolicy
from pii_masker.usability.tags import UsabilityTag


def compute(
    *,
    text: str,
    detections: Sequence[Detection],
    diarization_available: bool,
    asr_confidence: float | None,
    usability_policy: UsabilityPolicy,
    diarization_policy: DiarizationFallbackPolicy,
) -> tuple[UsabilityTag, bool]:
    """Return (tag, fallback_mode) for the masked utterance.

    `fallback_mode` is True iff we entered the FALLBACK_MODE branch — used
    by MaskingResult to expose whether the fallback signal fired.
    """
    # Priority 1: audio quality
    if (
        asr_confidence is not None
        and asr_confidence < usability_policy.asr_confidence_threshold
    ):
        return UsabilityTag.LOW_AUDIO_QUALITY, False

    # Priority 2: no diarization
    if not diarization_available:
        if _has_fallback_signal(text, diarization_policy.agent_question_patterns):
            return UsabilityTag.FALLBACK_MODE, True
        return UsabilityTag.NO_DIARIZATION, False

    # Priority 3: degraded masking density
    text_len = max(len(text), 1)
    density = len(detections) / text_len * 100
    if density > usability_policy.degraded_masking_threshold:
        return UsabilityTag.DEGRADED_MASKING, False

    return UsabilityTag.USABLE, False


def _has_fallback_signal(text: str, patterns: Sequence[Pattern[str]]) -> bool:
    return any(p.search(text) for p in patterns)

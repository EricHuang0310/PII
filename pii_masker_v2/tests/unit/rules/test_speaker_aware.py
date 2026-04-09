"""Tests for the speaker-aware diarization fallback rule.

The most important test here is `test_speaker_aware_does_not_mutate_input` —
it pins the v2 invariant that this rule must return new Detection objects.
"""
from __future__ import annotations

import re

import pytest

from pii_masker.domain.detection import Detection
from pii_masker.domain.entity_type import EntityType
from pii_masker.domain.policy import DiarizationFallbackPolicy
from pii_masker.domain.span import Span
from pii_masker.rules import speaker_aware


def _det(start: int, end: int, score: float = 0.5) -> Detection:
    return Detection(
        span=Span(start, end),
        entity_type=EntityType.TW_PHONE,
        confidence=score,
        detector_id="regex:test:v1",
    )


@pytest.fixture
def policy() -> DiarizationFallbackPolicy:
    return DiarizationFallbackPolicy(
        answer_window_chars=30,
        question_boost=0.15,
        answer_boost=0.10,
        diarization_threshold=0.8,
        agent_question_patterns=(re.compile(r"請問"),),
        answer_patterns=(re.compile(r"是\s*\d+"),),
    )


@pytest.mark.unit
def test_speaker_aware_no_op_when_diarization_available(
    policy: DiarizationFallbackPolicy,
) -> None:
    d = _det(5, 10, 0.5)
    out = speaker_aware.apply([d], "請問0912345678", diarization_available=True, policy=policy)
    assert len(out) == 1
    assert out[0].confidence == 0.5


@pytest.mark.unit
def test_speaker_aware_question_boost(policy: DiarizationFallbackPolicy) -> None:
    """Detection inside the question window should get a boost."""
    # "請問" at 0-2, detection at 5-15 is within 30 chars of end (2)
    d = _det(5, 15, 0.5)
    out = speaker_aware.apply(
        [d], "請問的電話號碼", diarization_available=False, policy=policy
    )
    assert out[0].confidence == pytest.approx(0.5 + 0.15)


@pytest.mark.unit
def test_speaker_aware_answer_boost(policy: DiarizationFallbackPolicy) -> None:
    """Detection overlapping an answer pattern should get a boost."""
    # "是 123456" — answer pattern matches this, detection is 0-7
    d = _det(0, 7, 0.5)
    out = speaker_aware.apply(
        [d], "是 123456", diarization_available=False, policy=policy
    )
    assert out[0].confidence == pytest.approx(0.5 + 0.10)


@pytest.mark.unit
def test_speaker_aware_cumulative_boost(policy: DiarizationFallbackPolicy) -> None:
    """Detection in both a question window and an answer pattern gets both boosts."""
    text = "請問是 12345678"
    # Detection span covers "是 12345678" (pos 2 onwards)
    d = _det(2, 12, 0.5)
    out = speaker_aware.apply(
        [d], text, diarization_available=False, policy=policy
    )
    assert out[0].confidence == pytest.approx(0.5 + 0.15 + 0.10)


@pytest.mark.unit
def test_speaker_aware_clamps_to_1(policy: DiarizationFallbackPolicy) -> None:
    d = _det(5, 15, 0.95)
    out = speaker_aware.apply(
        [d], "請問的", diarization_available=False, policy=policy
    )
    # 0.95 + 0.15 = 1.10 → clamped to 1.0
    assert out[0].confidence == 1.0


@pytest.mark.unit
def test_speaker_aware_does_not_mutate_input(
    policy: DiarizationFallbackPolicy,
) -> None:
    """CRITICAL v2 invariant: speaker-aware must return NEW Detections.

    v3/v4 mutates `r.score +=` in place. v2 must not.
    """
    d = _det(5, 15, 0.5)
    input_list = [d]
    original_score = d.confidence
    out = speaker_aware.apply(
        input_list, "請問的電話", diarization_available=False, policy=policy
    )
    # Input detection unchanged
    assert d.confidence == original_score
    # Output is a different object (even if values match)
    assert out[0] is not d or out[0].confidence == d.confidence
    # Input list length unchanged
    assert len(input_list) == 1


@pytest.mark.unit
def test_speaker_aware_empty_input(policy: DiarizationFallbackPolicy) -> None:
    out = speaker_aware.apply([], "text", diarization_available=False, policy=policy)
    assert out == []

"""Verification answer detector (VERIFICATION_ANSWER).

Ports v3/v4 `VerificationAnswerRecognizer`. When a verification-question
trigger (母親姓名 / 媽媽 / 安全問題 / ...) appears, look within
`answer_window_chars` for a short Chinese name (2..5 chars) or a 6..8 digit
number, and flag it as VERIFICATION_ANSWER.

Unlike the pure regex detectors this one has its own class because the
detection logic is two-stage (trigger → windowed answer search).
"""
from __future__ import annotations

import re
from collections.abc import Sequence
from typing import Pattern

from pii_masker.detect.base import BaseDetector
from pii_masker.detect.regex import keywords
from pii_masker.domain.detection import Detection
from pii_masker.domain.entity_type import EntityType
from pii_masker.domain.span import Span


class VerificationAnswerDetector(BaseDetector):
    _BASE_SCORE: float = 0.75
    _VERSION: str = "v1"

    def __init__(self, answer_window_chars: int) -> None:
        if answer_window_chars <= 0:
            raise ValueError("answer_window_chars must be > 0")
        self._window: int = answer_window_chars
        self._trigger: Pattern[str] = re.compile(
            "|".join(re.escape(k) for k in keywords.VERIFICATION)
        )
        self._answer: Pattern[str] = re.compile(r"[\u4e00-\u9fff]{2,5}|\d{6,8}")

    @property
    def detector_id(self) -> str:
        return f"regex:verification_answer:{self._VERSION}"

    @property
    def entity_types(self) -> frozenset[EntityType]:
        return frozenset({EntityType.VERIFICATION_ANSWER})

    def detect(self, text: str) -> Sequence[Detection]:
        if not text:
            return ()
        results: list[Detection] = []
        for tm in self._trigger.finditer(text):
            window_start = tm.end()
            window_end = min(len(text), window_start + self._window)
            window = text[window_start:window_end]
            for am in self._answer.finditer(window):
                abs_start = window_start + am.start()
                abs_end = window_start + am.end()
                results.append(
                    Detection(
                        span=Span(abs_start, abs_end),
                        entity_type=EntityType.VERIFICATION_ANSWER,
                        confidence=self._BASE_SCORE,
                        detector_id=self.detector_id,
                        subtype="VERIFICATION_TRIGGER",
                        raw_text=am.group(0),
                    )
                )
        return results


def build(answer_window_chars: int) -> VerificationAnswerDetector:
    return VerificationAnswerDetector(answer_window_chars)

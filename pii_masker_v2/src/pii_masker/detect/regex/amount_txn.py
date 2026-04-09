"""High-risk transaction amount detector (AMOUNT_TXN).

Ports v3/v4 `AmountTxnRecognizer`. Unlike plain `AMOUNT`, this always masks —
if a high-risk verb (轉帳/匯款/…) is near a number, the number is tagged
AMOUNT_TXN regardless of account/card proximity.

The verb list is policy-driven (not hardcoded) so it can be tuned per
deployment. Construct with `build(policy)` to get a properly-configured
detector.
"""
from __future__ import annotations

import re
from collections.abc import Sequence
from typing import Pattern

from pii_masker.detect.base import BaseDetector
from pii_masker.domain.detection import Detection
from pii_masker.domain.entity_type import EntityType
from pii_masker.domain.span import Span


class AmountTxnDetector(BaseDetector):
    """Detects amounts adjacent to high-risk transaction verbs."""

    _BASE_SCORE: float = 0.82
    _VERSION: str = "v1"

    def __init__(self, high_risk_verbs: Sequence[str]) -> None:
        if not high_risk_verbs:
            raise ValueError("AmountTxnDetector requires at least one verb")
        self._verbs: tuple[str, ...] = tuple(high_risk_verbs)
        self._pattern: Pattern[str] = _build_pattern(self._verbs)

    @property
    def detector_id(self) -> str:
        return f"regex:amount_txn:{self._VERSION}"

    @property
    def entity_types(self) -> frozenset[EntityType]:
        return frozenset({EntityType.AMOUNT_TXN})

    def detect(self, text: str) -> Sequence[Detection]:
        if not text:
            return ()
        results: list[Detection] = []
        for m in self._pattern.finditer(text):
            num = m.group(1) or m.group(2)
            if not num:
                continue
            idx = text.find(num, m.start())
            if idx == -1:
                continue
            results.append(
                Detection(
                    span=Span(idx, idx + len(num)),
                    entity_type=EntityType.AMOUNT_TXN,
                    confidence=self._BASE_SCORE,
                    detector_id=self.detector_id,
                    subtype="AMOUNT_TXN_VERB",
                    raw_text=num,
                )
            )
        return results


def _build_pattern(verbs: Sequence[str]) -> Pattern[str]:
    """Build the verb↔amount adjacency regex.

    Matches either:
    - VERB . . . NUMBER  (verb before number, within 20 chars)
    - NUMBER . . . VERB  (number before verb, within 10 chars)
    """
    verb_alt = "|".join(re.escape(v) for v in verbs)
    return re.compile(
        f"(?:{verb_alt}).{{0,20}}?(\\d+(?:,\\d{{3}})*(?:元|塊|NTD|NT)?)"
        f"|(\\d+(?:,\\d{{3}})*(?:元|塊|NTD|NT)?).{{0,10}}?(?:{verb_alt})"
    )


def build(high_risk_verbs: Sequence[str]) -> AmountTxnDetector:
    """Factory for building an AmountTxnDetector from a policy's verb list."""
    return AmountTxnDetector(high_risk_verbs)

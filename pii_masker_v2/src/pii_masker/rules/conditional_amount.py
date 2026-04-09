"""Conditional AMOUNT masking rule.

Ports v3/v4 `_apply_conditional_amount_masking`:

- If no trigger entity (account/card) is present, drop ALL `AMOUNT` detections
- Otherwise, keep only `AMOUNT` detections whose span is within
  `proximity_chars` of a trigger span

`AMOUNT_TXN` is unaffected by this rule — those are always kept (they were
emitted by the high-risk-verb detector and should always be masked).
"""
from __future__ import annotations

from collections.abc import Sequence

from pii_masker.domain.detection import Detection
from pii_masker.domain.entity_type import EntityType
from pii_masker.domain.policy import ConditionalAmountPolicy


def apply(
    detections: Sequence[Detection],
    policy: ConditionalAmountPolicy,
) -> list[Detection]:
    """Return a new list with AMOUNT detections filtered by proximity."""
    triggers = [d for d in detections if d.entity_type in policy.trigger_entities]
    if not triggers:
        return [d for d in detections if d.entity_type is not EntityType.AMOUNT]

    kept: list[Detection] = []
    for d in detections:
        if d.entity_type is not EntityType.AMOUNT:
            kept.append(d)
            continue
        # Keep only if ANY trigger span is within proximity_chars of this one.
        if _near_any(d, triggers, policy.proximity_chars):
            kept.append(d)
    return kept


def _near_any(
    amount: Detection, triggers: Sequence[Detection], max_chars: int
) -> bool:
    for trg in triggers:
        if abs(amount.span.start - trg.span.start) <= max_chars:
            return True
    return False

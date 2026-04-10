"""Composite priority score — final tiebreaker in the conflict resolver.

Ports v3/v4 `_compute_priority_score`:

    final = priority × 0.4
          + risk × 10 × 0.4
          + presidio_score × 10 × 0.1
          + keyword_bonus × 0.1

Keyword context is detected via the detection's confidence relative to
`_KEYWORD_SCORE_THRESHOLD`. The v3/v4 heuristic is the same.
"""
from __future__ import annotations

from pii_masker.domain.detection import Detection
from pii_masker.domain.policy import MaskingPolicy

_KEYWORD_SCORE_THRESHOLD: float = 0.70
_KEYWORD_BONUS: float = 10.0


def has_keyword_context(detection: Detection) -> bool:
    """Heuristic: if confidence is ≥ 0.70 we assume a context keyword fired.

    This mirrors v3/v4's heuristic. Detectors that apply keyword boosts
    push their scores above this threshold.
    """
    return detection.confidence >= _KEYWORD_SCORE_THRESHOLD


def compute_score(detection: Detection, policy: MaskingPolicy) -> float:
    """Compute the composite priority score for a detection."""
    priority = policy.priority_of(detection.entity_type)
    risk = policy.risk_of(detection.entity_type) * 10
    p_score = detection.confidence * 10
    kw_bonus = _KEYWORD_BONUS if has_keyword_context(detection) else 0.0
    return priority * 0.4 + risk * 0.4 + p_score * 0.1 + kw_bonus * 0.1

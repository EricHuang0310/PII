"""Speaker-aware rule — boost confidence based on diarization fallback signals.

CRITICAL v2 contract: this function MUST return new Detection objects. It
must NOT mutate the input list or any element. This closes the v3/v4
`r.score = min(1.0, r.score + 0.15)` in-place mutation bug.

When diarization is available, the rule is a no-op (the caller has real
speaker labels and doesn't need fallback scoring).

When diarization is NOT available, the rule:
1. Finds every agent-question match in the text
2. Boosts every detection whose span falls inside the window after the
   question by `question_boost`
3. Finds every answer-pattern match
4. Boosts every detection whose span overlaps an answer match by
   `answer_boost`

Both boosts are cumulative (a detection that's in both windows gets both
bumps). Scores are clamped to [0, 1] by `Detection.boosted`.
"""
from __future__ import annotations

from collections.abc import Sequence

from pii_masker.domain.detection import Detection
from pii_masker.domain.policy import DiarizationFallbackPolicy


def apply(
    detections: Sequence[Detection],
    text: str,
    diarization_available: bool,
    policy: DiarizationFallbackPolicy,
) -> list[Detection]:
    """Return a new list of detections with fallback boosts applied."""
    if diarization_available or not detections:
        # Return a fresh list (still immutable elements) so callers always
        # get back a list they can mutate without affecting upstream state.
        return list(detections)

    boosted: list[Detection] = []
    for d in detections:
        delta = _compute_boost(d, text, policy)
        if delta > 0.0:
            boosted.append(d.boosted(delta))
        else:
            boosted.append(d)
    return boosted


def _compute_boost(
    detection: Detection,
    text: str,
    policy: DiarizationFallbackPolicy,
) -> float:
    total = 0.0
    # Question window boost — any detection within policy.answer_window_chars
    # after an agent question gets +policy.question_boost.
    for q_pattern in policy.agent_question_patterns:
        for m in q_pattern.finditer(text):
            window_start = m.end()
            window_end = window_start + policy.answer_window_chars
            if window_start <= detection.span.start <= window_end:
                total += policy.question_boost
                break  # one boost per pattern is enough

    # Answer pattern boost — any detection whose span overlaps an answer
    # match gets +policy.answer_boost.
    for a_pattern in policy.answer_patterns:
        for m in a_pattern.finditer(text):
            if m.start() <= detection.span.start < m.end():
                total += policy.answer_boost
                break

    return total

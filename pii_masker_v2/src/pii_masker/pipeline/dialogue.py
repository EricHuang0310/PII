"""Dialogue-level wrapper — shares one PseudonymTracker across turns.

Ports v3/v4 `mask_dialogue` with the labeled-ratio diarization threshold
fix preserved (Issue 3).
"""
from __future__ import annotations

from collections.abc import Sequence

from pii_masker.audit.trace import new_trace_id, new_turn_id
from pii_masker.domain.dialogue import DialogueTurn, Speaker
from pii_masker.domain.result import MaskingResult
from pii_masker.pipeline.masker import MaskingPipeline
from pii_masker.tokenize.tracker import PseudonymTracker


def mask_dialogue(
    turns: Sequence[DialogueTurn],
    pipeline: MaskingPipeline,
    *,
    session_id: str = "",
    diarization_threshold: float | None = None,
) -> list[MaskingResult]:
    """Mask every turn of a dialogue, sharing one PseudonymTracker.

    `diarization_available` is computed from the labeled-speaker ratio —
    NOT from `any(...)`, which was the v3/v4 Issue 3 bug. The policy's
    `diarization_fallback.diarization_threshold` is the default cutoff.
    """
    if not turns:
        return []

    threshold = (
        diarization_threshold
        if diarization_threshold is not None
        else pipeline.policy.diarization_fallback.diarization_threshold
    )

    labeled = sum(
        1 for t in turns if t.speaker in {Speaker.AGENT, Speaker.CUSTOMER}
    )
    ratio = labeled / max(len(turns), 1)
    diarization_available = ratio >= threshold

    tracker = PseudonymTracker(session_id=session_id)
    trace_id = new_trace_id()

    return [
        pipeline.mask(
            text=t.text,
            session_id=session_id,
            turn_id=t.turn_id or new_turn_id(),
            trace_id=trace_id,
            speaker=t.speaker,
            diarization_available=diarization_available,
            tracker=tracker,
            asr_confidence=t.asr_confidence,
        )
        for t in turns
    ]

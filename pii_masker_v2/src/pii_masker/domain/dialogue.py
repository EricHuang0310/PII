"""Dialogue types — Speaker enum and frozen DialogueTurn."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class Speaker(str, Enum):
    """Who is speaking in a dialogue turn.

    UNKNOWN is used when diarization is missing; the pipeline falls back to
    question/answer pattern detection when the ratio of labeled speakers drops
    below the diarization_threshold.
    """

    AGENT = "AGENT"
    CUSTOMER = "CUSTOMER"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True, slots=True)
class DialogueTurn:
    """One utterance in a dialogue.

    Mirrors the v3/v4 `pipeline.DialogueTurn` dataclass but:
    - Speaker is an Enum, not a raw string
    - fields are frozen
    - asr_confidence is explicit Optional[float] rather than None-by-default
    """

    text: str
    speaker: Speaker = Speaker.UNKNOWN
    start_time: float | None = None
    end_time: float | None = None
    asr_confidence: float | None = None
    turn_id: str = ""

    def __post_init__(self) -> None:
        if self.asr_confidence is not None and not 0.0 <= self.asr_confidence <= 1.0:
            raise ValueError(
                f"DialogueTurn.asr_confidence must be in [0, 1], "
                f"got {self.asr_confidence}"
            )
        if (
            self.start_time is not None
            and self.end_time is not None
            and self.end_time < self.start_time
        ):
            raise ValueError(
                f"DialogueTurn.end_time ({self.end_time}) must be >= "
                f"start_time ({self.start_time})"
            )

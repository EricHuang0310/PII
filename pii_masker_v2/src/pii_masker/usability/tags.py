"""UsabilityTag — closed set of usability labels for masked transcripts.

Mirrors the v3/v4 `config.UsabilityTag` class but as an Enum so invalid strings
cannot leak into audit rows.
"""
from __future__ import annotations

from enum import Enum


class UsabilityTag(str, Enum):
    """Closed set of usability labels."""

    USABLE = "USABLE"
    DEGRADED_MASKING = "DEGRADED_MASKING"  # > threshold entities per 100 chars
    NO_DIARIZATION = "NO_DIARIZATION"      # no speaker labels, no fallback signal
    FALLBACK_MODE = "FALLBACK_MODE"        # no speaker labels, but fallback patterns fired
    LOW_AUDIO_QUALITY = "LOW_AUDIO_QUALITY"  # ASR confidence below threshold

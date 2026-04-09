"""Tests for DialogueTurn and Speaker."""
from __future__ import annotations

import pytest

from pii_masker.domain.dialogue import DialogueTurn, Speaker


@pytest.mark.unit
def test_dialogue_turn_default_speaker_is_unknown() -> None:
    t = DialogueTurn(text="hello")
    assert t.speaker is Speaker.UNKNOWN


@pytest.mark.unit
def test_dialogue_turn_explicit_speaker() -> None:
    t = DialogueTurn(text="您好", speaker=Speaker.AGENT)
    assert t.speaker is Speaker.AGENT


@pytest.mark.unit
def test_dialogue_turn_rejects_invalid_asr_confidence() -> None:
    with pytest.raises(ValueError, match=r"asr_confidence must be in \[0, 1\]"):
        DialogueTurn(text="...", asr_confidence=1.2)


@pytest.mark.unit
def test_dialogue_turn_rejects_end_time_before_start() -> None:
    with pytest.raises(ValueError, match="end_time .* must be >= start_time"):
        DialogueTurn(text="...", start_time=5.0, end_time=2.0)


@pytest.mark.unit
def test_dialogue_turn_is_frozen() -> None:
    t = DialogueTurn(text="hi")
    with pytest.raises(Exception):
        t.text = "changed"  # type: ignore[misc]


@pytest.mark.unit
def test_speaker_enum_values() -> None:
    assert Speaker.AGENT == "AGENT"
    assert Speaker.CUSTOMER == "CUSTOMER"
    assert Speaker.UNKNOWN == "UNKNOWN"

"""Tests for VerificationAnswerDetector."""
from __future__ import annotations

import pytest

from pii_masker.detect.regex.verification_answer import build


@pytest.mark.unit
def test_verification_answer_basic() -> None:
    """Port of v3/v4 behavior: greedy match over the trigger window.

    The v3/v4 regex `[\u4e00-\u9fff]{2,5}` is greedy, so it matches the first
    5 Chinese characters after the trigger ("姓名是陳美"), not just the
    3-character name. This test pins that byte-exact behavior so any future
    intent to "fix" it must be an explicit decision, not a silent drift.
    """
    det = build(answer_window_chars=30)
    dets = list(det.detect("母親姓名是陳美玲"))
    assert len(dets) >= 1
    # Greedy 5-char match starting immediately after the trigger
    assert dets[0].raw_text == "姓名是陳美"


@pytest.mark.unit
def test_verification_answer_numeric_dob() -> None:
    det = build(answer_window_chars=30)
    dets = list(det.detect("母親生日19850501"))
    assert any("1985050" in d.raw_text or "19850501" in d.raw_text for d in dets)


@pytest.mark.unit
def test_verification_answer_empty_text() -> None:
    det = build(answer_window_chars=30)
    assert det.detect("") == ()


@pytest.mark.unit
def test_verification_answer_no_trigger_no_match() -> None:
    det = build(answer_window_chars=30)
    assert list(det.detect("我叫王小明")) == []


@pytest.mark.unit
def test_verification_answer_rejects_non_positive_window() -> None:
    with pytest.raises(ValueError, match="> 0"):
        build(answer_window_chars=0)

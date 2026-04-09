"""Tests for STT filler-repeat collapsing."""
from __future__ import annotations

import pytest

from pii_masker.normalize.stt_filler import clean_filler_repeats


@pytest.mark.unit
def test_filler_empty() -> None:
    assert clean_filler_repeats("") == ""


@pytest.mark.unit
def test_filler_collapses_3_plus_repeats_to_2() -> None:
    assert clean_filler_repeats("嗯嗯嗯嗯") == "嗯嗯"
    assert clean_filler_repeats("啊啊啊") == "啊啊"


@pytest.mark.unit
def test_filler_leaves_2_repeats_alone() -> None:
    assert clean_filler_repeats("嗯嗯") == "嗯嗯"


@pytest.mark.unit
def test_filler_leaves_1_repeat_alone() -> None:
    assert clean_filler_repeats("嗯") == "嗯"


@pytest.mark.unit
def test_filler_does_not_collapse_generic_cjk() -> None:
    """CRITICAL: generic CJK repeats must NOT be collapsed.

    This is the v3/v4 Issue 7 fix — legitimate PII like a 4-digit account
    suffix that happens to have a repeated digit was being destroyed by
    overly-aggressive filler collapsing.
    """
    assert clean_filler_repeats("三三三五") == "三三三五"
    assert clean_filler_repeats("王王王") == "王王王"


@pytest.mark.unit
def test_filler_handles_mixed_fillers() -> None:
    assert clean_filler_repeats("嗯嗯嗯這個啊啊啊") == "嗯嗯這個啊啊"

"""Tests for the composed normalize() pipeline.

The most important test in this file is `test_numeral_before_roc` — it pins
the v3/v4 Issue 1 fix. Reordering those two steps is a critical regression.
"""
from __future__ import annotations

import pytest
from hypothesis import given
from hypothesis import strategies as st

from pii_masker.normalize.compose import normalize


@pytest.mark.unit
def test_normalize_empty() -> None:
    assert normalize("") == ""


@pytest.mark.unit
def test_normalize_passthrough_plain_text() -> None:
    assert normalize("hello world") == "hello world"


@pytest.mark.unit
def test_normalize_numeral_before_roc() -> None:
    """LOAD-BEARING INVARIANT: Chinese numerals must run BEFORE ROC year.

    If the order is reversed, "民國一一三年" stays as-is because the ROC
    converter only handles Arabic digits. This test is the guardrail.
    """
    assert normalize("民國一一三年") == "2024年"


@pytest.mark.unit
def test_normalize_roc_year_already_arabic() -> None:
    assert normalize("生日是民國74年") == "生日是1985年"


@pytest.mark.unit
def test_normalize_fullwidth_then_digits() -> None:
    assert normalize("卡號１２３４") == "卡號1234"


@pytest.mark.unit
def test_normalize_preserves_legit_repeated_digits() -> None:
    """Step 7 fix: STT filler collapse must not break "三三三五"."""
    assert normalize("帳號三三三五") == "帳號3335"


@pytest.mark.unit
def test_normalize_stt_fillers_still_collapsed() -> None:
    assert normalize("嗯嗯嗯嗯我叫王小明") == "嗯嗯我叫王小明"


@pytest.mark.unit
def test_normalize_full_dialogue_realistic() -> None:
    got = normalize("生日是民國七十四年五月一日")
    assert "1985" in got
    assert "5月" in got
    assert "1日" in got


# ── Property: idempotence ────────────────────────────────────────
@pytest.mark.property
@given(st.text())
def test_normalize_is_idempotent(text: str) -> None:
    """normalize(normalize(x)) == normalize(x) — must converge in one step."""
    once = normalize(text)
    twice = normalize(once)
    assert twice == once

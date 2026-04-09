"""Tests for Chinese numeral → Arabic conversion."""
from __future__ import annotations

import pytest

from pii_masker.normalize.zh_numeral import to_arabic


@pytest.mark.unit
def test_zh_numeral_empty() -> None:
    assert to_arabic("") == ""


# ── Step A: positional numerals ──────────────────────────────────
@pytest.mark.unit
def test_zh_numeral_positional_74() -> None:
    assert to_arabic("七十四") == "74"


@pytest.mark.unit
def test_zh_numeral_positional_leading_ten() -> None:
    """十X at the start should equal 1×10 + X."""
    assert to_arabic("十三") == "13"


@pytest.mark.unit
def test_zh_numeral_positional_hundreds() -> None:
    assert to_arabic("一百零三") == "103"


@pytest.mark.unit
def test_zh_numeral_positional_thousands() -> None:
    assert to_arabic("二千") == "2000"


# ── Step B: single digit + time unit ─────────────────────────────
@pytest.mark.unit
def test_zh_numeral_single_digit_time_unit() -> None:
    assert to_arabic("三月") == "3月"
    assert to_arabic("一日") == "1日"
    assert to_arabic("五號") == "5號"
    assert to_arabic("六點") == "6點"


# ── Step C: consecutive plain digits ─────────────────────────────
@pytest.mark.unit
def test_zh_numeral_consecutive_digits() -> None:
    assert to_arabic("一一三") == "113"


@pytest.mark.unit
def test_zh_numeral_consecutive_account_suffix() -> None:
    """Legitimate PII data like a 4-digit account suffix must be converted."""
    assert to_arabic("三三三五") == "3335"


# ── Mixed / boundary ─────────────────────────────────────────────
@pytest.mark.unit
def test_zh_numeral_pure_arabic_untouched() -> None:
    assert to_arabic("abc123") == "abc123"


@pytest.mark.unit
def test_zh_numeral_single_digit_without_unit_untouched() -> None:
    """A lone 一 without a time-unit suffix should stay as-is."""
    # Step C only fires on 2+ consecutive digits.
    assert to_arabic("一") == "一"


@pytest.mark.unit
def test_zh_numeral_roc_year_input() -> None:
    """"民國一一三年" should become "民國113年" (Step C handles the digits)."""
    assert to_arabic("民國一一三年") == "民國113年"

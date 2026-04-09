"""Tests for TWCreditCardDetector (including optional Luhn validation)."""
from __future__ import annotations

import pytest

from pii_masker.detect.regex.tw_credit_card import TWCreditCardDetector, build
from pii_masker.detect.regex.validators import luhn_valid


@pytest.mark.unit
def test_credit_card_basic_match() -> None:
    # 4111111111111111 is the canonical Visa test card (Luhn-valid)
    dets = list(TWCreditCardDetector().detect("卡號4111111111111111"))
    assert len(dets) == 1
    assert dets[0].raw_text == "4111111111111111"


@pytest.mark.unit
def test_credit_card_rejects_less_than_16() -> None:
    assert list(TWCreditCardDetector().detect("卡號123456789012345")) == []


@pytest.mark.unit
def test_luhn_valid_cases() -> None:
    assert luhn_valid("4111111111111111") is True  # Visa test
    assert luhn_valid("5555555555554444") is True  # MasterCard test
    assert luhn_valid("4111111111111112") is False


@pytest.mark.unit
def test_build_strict_drops_luhn_fail() -> None:
    det = build(strict=True)
    good = list(det.detect("卡號4111111111111111"))
    bad = list(det.detect("卡號4111111111111112"))
    assert len(good) == 1
    assert bad == []


@pytest.mark.unit
def test_build_non_strict_keeps_all() -> None:
    det = build(strict=False)
    assert len(list(det.detect("卡號4111111111111112"))) == 1

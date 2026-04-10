"""Tests for TWBankAccountDetector."""
from __future__ import annotations

import pytest

from pii_masker.detect.regex.tw_bank_account import TWBankAccountDetector


@pytest.mark.unit
def test_bank_account_basic() -> None:
    dets = list(TWBankAccountDetector().detect("帳號1234567890"))
    assert len(dets) == 1
    assert dets[0].raw_text == "1234567890"


@pytest.mark.unit
def test_bank_account_rejects_mobile_number() -> None:
    """09... is a mobile number, not a bank account.

    The negative lookahead in the regex prevents this false positive.
    """
    assert list(TWBankAccountDetector().detect("0912345678")) == []


@pytest.mark.unit
def test_bank_account_allows_longer_numbers() -> None:
    assert len(list(TWBankAccountDetector().detect("帳號12345678901234"))) == 1


@pytest.mark.unit
def test_bank_account_rejects_too_short() -> None:
    assert list(TWBankAccountDetector().detect("帳號123456789")) == []  # only 9 digits

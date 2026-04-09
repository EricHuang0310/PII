"""Tests for the masking-token regex helpers."""
from __future__ import annotations

import pytest

from pii_masker.verify.token_regex import is_token, span_is_inside_token


@pytest.mark.unit
@pytest.mark.parametrize(
    "s,expected",
    [
        ("[NAME]", True),
        ("[CARD]", True),
        ("[AMOUNT_TXN]", True),
        ("[ADDRESS]", True),
        ("name", False),
        ("[name]", False),   # lowercase — not a token
        ("[]", False),
        ("[NAME", False),
        ("[A B]", False),
    ],
)
def test_is_token(s: str, expected: bool) -> None:
    assert is_token(s) is expected


@pytest.mark.unit
def test_span_inside_token() -> None:
    text = "我叫[NAME]卡號[CARD]"
    # [NAME] occupies positions 2..8 (6 chars)
    assert span_is_inside_token(text, 2, 8) is True
    assert span_is_inside_token(text, 3, 7) is True   # interior
    assert span_is_inside_token(text, 0, 2) is False  # before the token
    assert span_is_inside_token(text, 8, 10) is False  # between tokens

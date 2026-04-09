"""Tests for the Step 7 leak scanner."""
from __future__ import annotations

import pytest

from pii_masker.detect.registry import build_regex_detectors
from pii_masker.verify.leak_scanner import scan, strip_token_contents


@pytest.mark.unit
def test_scan_clean_masked_text_returns_empty(default_policy) -> None:  # type: ignore[no-untyped-def]
    detectors = build_regex_detectors(default_policy)
    # All PII is inside tokens — scanner should find nothing
    masked = "我叫[NAME]卡號[CARD]電話[PHONE]"
    assert scan(masked, detectors) == []


@pytest.mark.unit
def test_scan_detects_residual_phone(default_policy) -> None:  # type: ignore[no-untyped-def]
    detectors = build_regex_detectors(default_policy)
    # A phone number slipped through the masker
    leaked = "我叫[NAME]電話0912345678"
    residual = scan(leaked, detectors)
    phone_leaks = [d for d in residual if d.entity_type.value == "TW_PHONE"]
    assert len(phone_leaks) >= 1


@pytest.mark.unit
def test_scan_detects_residual_credit_card(default_policy) -> None:  # type: ignore[no-untyped-def]
    detectors = build_regex_detectors(default_policy)
    leaked = "卡號4111111111111111"  # no masking at all
    residual = scan(leaked, detectors)
    card_leaks = [d for d in residual if d.entity_type.value == "TW_CREDIT_CARD"]
    assert len(card_leaks) >= 1


@pytest.mark.unit
def test_scan_empty_text_returns_empty(default_policy) -> None:  # type: ignore[no-untyped-def]
    detectors = build_regex_detectors(default_policy)
    assert scan("", detectors) == []


@pytest.mark.unit
def test_strip_token_contents_blanks_tokens() -> None:
    out = strip_token_contents("abc[NAME]def")
    assert out == "abc      def"  # [NAME] = 6 chars → 6 spaces
    assert len(out) == len("abc[NAME]def")

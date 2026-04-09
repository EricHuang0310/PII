"""Tests for TWPhoneDetector."""
from __future__ import annotations

import pytest

from pii_masker.detect.regex.tw_phone import TWPhoneDetector


@pytest.mark.unit
def test_phone_mobile() -> None:
    dets = list(TWPhoneDetector().detect("請打0912345678"))
    assert len(dets) == 1
    assert dets[0].subtype == "MOBILE"


@pytest.mark.unit
def test_phone_landline() -> None:
    dets = list(TWPhoneDetector().detect("公司電話0223456789"))
    assert any(d.subtype == "LANDLINE" for d in dets)


@pytest.mark.unit
def test_phone_context_boosts_mobile() -> None:
    with_ctx = list(TWPhoneDetector().detect("電話0912345678"))
    without_ctx = list(TWPhoneDetector().detect("0912345678"))
    assert with_ctx[0].confidence > without_ctx[0].confidence

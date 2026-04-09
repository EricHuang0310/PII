"""Tests for TWIDDetector (including optional checksum validation)."""
from __future__ import annotations

import pytest

from pii_masker.detect.regex.tw_id import TWIDDetector, build
from pii_masker.detect.regex.validators import tw_id_valid


@pytest.mark.unit
def test_tw_id_basic_match() -> None:
    dets = list(TWIDDetector().detect("身分證A123456789"))
    assert len(dets) == 1
    assert dets[0].raw_text == "A123456789"


@pytest.mark.unit
def test_tw_id_rejects_wrong_format() -> None:
    """A leading letter followed by something other than 1/2 should not match."""
    assert list(TWIDDetector().detect("A923456789")) == []


@pytest.mark.unit
def test_tw_id_valid_checksum_for_known_good_id() -> None:
    # A123456789 is a canonical test ID that passes the official checksum.
    assert tw_id_valid("A123456789") is True


@pytest.mark.unit
def test_tw_id_invalid_checksum() -> None:
    assert tw_id_valid("A123456780") is False


@pytest.mark.unit
def test_build_with_strict_drops_invalid_checksum() -> None:
    """Strict mode drops regex hits whose checksum is wrong."""
    det = build(strict=True)
    # A123456789 is valid, A123456780 is not
    good = list(det.detect("身分證A123456789"))
    bad = list(det.detect("身分證A123456780"))
    assert len(good) == 1
    assert bad == []


@pytest.mark.unit
def test_build_without_strict_keeps_all_hits() -> None:
    det = build(strict=False)
    assert len(list(det.detect("身分證A123456780"))) == 1  # regex match, no validation

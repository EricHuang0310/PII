"""Tests for RegexDetector base class behavior."""
from __future__ import annotations

import pytest

from pii_masker.detect.regex.base import RegexDetector, RegexPattern
from pii_masker.domain.entity_type import EntityType


class _PhoneLike(RegexDetector):
    entity_type = EntityType.TW_PHONE
    patterns = (RegexPattern.compile("MOBILE", r"09\d{8}", 0.85),)
    context_keywords = ("電話", "手機")
    context_window = 10
    context_boost = 0.1
    version = "v-test"


@pytest.mark.unit
def test_base_returns_empty_on_empty_text() -> None:
    d = _PhoneLike()
    assert d.detect("") == ()


@pytest.mark.unit
def test_base_finds_matches() -> None:
    d = _PhoneLike()
    dets = list(d.detect("我的號碼0912345678"))
    assert len(dets) == 1
    assert dets[0].entity_type is EntityType.TW_PHONE
    assert dets[0].span.start == 4
    assert dets[0].span.end == 14
    assert dets[0].raw_text == "0912345678"


@pytest.mark.unit
def test_base_context_boost_fires_when_keyword_nearby() -> None:
    d = _PhoneLike()
    with_context = list(d.detect("電話0912345678"))
    without_context = list(d.detect("0912345678"))
    assert with_context[0].confidence > without_context[0].confidence
    assert with_context[0].confidence == pytest.approx(0.85 + 0.1)
    assert without_context[0].confidence == pytest.approx(0.85)


@pytest.mark.unit
def test_base_context_boost_clamps_to_1() -> None:
    class _AlreadyHigh(_PhoneLike):
        patterns = (RegexPattern.compile("X", r"09\d{8}", 0.95),)
        context_boost = 0.20

    assert list(_AlreadyHigh().detect("電話0912345678"))[0].confidence == 1.0


@pytest.mark.unit
def test_base_post_filter_drops_matches() -> None:
    d = _PhoneLike(
        post_filter=lambda det, text: det.raw_text != "0912345678",
    )
    assert list(d.detect("0912345678")) == []
    assert len(list(d.detect("0987654321"))) == 1


@pytest.mark.unit
def test_base_detector_id_format() -> None:
    assert _PhoneLike().detector_id == "regex:tw_phone:v-test"


@pytest.mark.unit
def test_base_rejects_empty_patterns() -> None:
    class _Empty(RegexDetector):
        entity_type = EntityType.PERSON
        patterns = ()

    with pytest.raises(ValueError, match="at least one pattern"):
        _Empty()

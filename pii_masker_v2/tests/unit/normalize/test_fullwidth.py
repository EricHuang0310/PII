"""Tests for full-width → half-width conversion."""
from __future__ import annotations

import pytest

from pii_masker.normalize.fullwidth import to_halfwidth


@pytest.mark.unit
def test_fullwidth_empty() -> None:
    assert to_halfwidth("") == ""


@pytest.mark.unit
def test_fullwidth_digits() -> None:
    assert to_halfwidth("１２３４") == "1234"


@pytest.mark.unit
def test_fullwidth_letters() -> None:
    assert to_halfwidth("ＡＢＣｄｅｆ") == "ABCdef"


@pytest.mark.unit
def test_fullwidth_punct() -> None:
    assert to_halfwidth("（）！？") == "()!?"


@pytest.mark.unit
def test_fullwidth_ideographic_space() -> None:
    assert to_halfwidth("你好\u3000世界") == "你好 世界"


@pytest.mark.unit
def test_fullwidth_mixed() -> None:
    assert to_halfwidth("卡號１２３ＡＢ") == "卡號123AB"


@pytest.mark.unit
def test_fullwidth_preserves_chinese_characters() -> None:
    assert to_halfwidth("王小明") == "王小明"

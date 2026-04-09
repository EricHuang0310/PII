"""Tests for ROC year → CE year conversion."""
from __future__ import annotations

import pytest

from pii_masker.normalize.roc_year import to_ce_year


@pytest.mark.unit
def test_roc_year_empty() -> None:
    assert to_ce_year("") == ""


@pytest.mark.unit
def test_roc_year_basic() -> None:
    assert to_ce_year("民國113年") == "2024年"


@pytest.mark.unit
def test_roc_year_民國_with_國_char() -> None:
    assert to_ce_year("民國113年") == "2024年"


@pytest.mark.unit
def test_roc_year_lower_bound() -> None:
    """ROC 10 (CE 1921) is the documented minimum."""
    assert to_ce_year("民國10年") == "1921年"


@pytest.mark.unit
def test_roc_year_upper_bound() -> None:
    """ROC 150 (CE 2061) is the documented maximum."""
    assert to_ce_year("民國150年") == "2061年"


@pytest.mark.unit
def test_roc_year_below_range_passthrough() -> None:
    """Below-range numbers are left alone — they're probably not years."""
    assert to_ce_year("民國05年") == "民國05年"


@pytest.mark.unit
def test_roc_year_above_range_passthrough() -> None:
    assert to_ce_year("民國999年") == "民國999年"


@pytest.mark.unit
def test_roc_year_does_not_parse_chinese_numerals() -> None:
    """ROC year converter only handles Arabic digits.

    This is deliberate — the pipeline runs zh_numeral.to_arabic() FIRST, so
    by the time this function is called the digits are already Arabic.
    """
    # "民國一一三年" contains no Arabic digits → no conversion here.
    assert to_ce_year("民國一一三年") == "民國一一三年"

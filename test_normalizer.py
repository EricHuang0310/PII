"""
normalizer.py regression tests.

覆蓋：
  - 全形 → 半形
  - 中文數字 → 阿拉伯數字（位值結構 / 時間單位詞 / 逐字連續）
  - 民國年 → 西元年（含 Issue 1 critical path：中文數字 → ROC 順序）
  - STT 語助詞壓縮（Issue 7 invariant：只壓縮語助詞，不動一般中文）
  - 空白正規化
  - 綜合情境

執行：pytest test_normalizer.py -v
"""
from __future__ import annotations

import pytest

from normalizer import normalize, _parse_zh_number, _zh_digits_to_arabic, _clean_stt_repeats


# ══════════════════════════════════════════════════════════════
# 全形 → 半形
# ══════════════════════════════════════════════════════════════

def test_fullwidth_digits():
    assert normalize("１２３４５") == "12345"


def test_fullwidth_letters():
    assert normalize("ＡＢＣａｂｃ") == "ABCabc"


def test_fullwidth_space():
    assert normalize("台\u3000北") == "台 北"


def test_fullwidth_punctuation():
    assert normalize("您好！謝謝（確認）") == "您好!謝謝(確認)"


# ══════════════════════════════════════════════════════════════
# 中文數字 → 阿拉伯數字
# ══════════════════════════════════════════════════════════════

def test_parse_zh_number_with_position():
    assert _parse_zh_number("七十四") == "74"
    assert _parse_zh_number("二十六") == "26"
    assert _parse_zh_number("一百零三") == "103"
    assert _parse_zh_number("一千") == "1000"


def test_parse_zh_number_leading_ten():
    """「十X」開頭應視為 1×10 + X，不是 0×10 + X。"""
    assert _parse_zh_number("十五") == "15"
    assert _parse_zh_number("十") == "10"


def test_zh_digits_single_plus_time_unit():
    assert _zh_digits_to_arabic("三月") == "3月"
    assert _zh_digits_to_arabic("一日") == "1日"
    assert _zh_digits_to_arabic("五號") == "5號"
    assert _zh_digits_to_arabic("六點") == "6點"


def test_zh_digits_consecutive():
    """純逐字中文數字轉為阿拉伯數字（CLAUDE.md 明示：STT 不壓縮數字）。"""
    assert _zh_digits_to_arabic("一一三") == "113"
    assert _zh_digits_to_arabic("三三三五") == "3335"
    assert _zh_digits_to_arabic("零九一二") == "0912"


def test_zh_digits_not_triggered_by_single_digit():
    """單個中文數字（不接單位）不應觸發轉換。"""
    assert _zh_digits_to_arabic("三") == "三"


# ══════════════════════════════════════════════════════════════
# 民國年 → 西元年
# ══════════════════════════════════════════════════════════════

def test_roc_year_arabic_input():
    assert "2024年" in normalize("民國113年生")


def test_roc_year_via_zh_digits_issue1():
    """
    Issue 1 critical path：中文數字必須先於 ROC 轉換，
    否則「民國一一三年」無法被識別為民國 113 年。
    """
    assert "2024年" in normalize("民國一一三年生")


def test_roc_year_with_position_zh_number():
    """民國七十四年 → 1985年。"""
    assert "1985年" in normalize("民國七十四年")


def test_roc_year_out_of_range_low():
    """民國 < 10 視為可疑（可能是月日誤判），不轉換。"""
    assert "民國5年" in normalize("民國5年")


def test_roc_year_out_of_range_high():
    """民國 > 150 不轉換。"""
    assert "民國200年" in normalize("民國200年")


def test_roc_year_boundary_10():
    assert "1921年" in normalize("民國10年")


def test_roc_year_boundary_150():
    assert "2061年" in normalize("民國150年")


# ══════════════════════════════════════════════════════════════
# STT 語助詞壓縮（Issue 7 invariant）
# ══════════════════════════════════════════════════════════════

def test_stt_filler_compressed():
    assert _clean_stt_repeats("嗯嗯嗯嗯") == "嗯嗯"
    assert _clean_stt_repeats("啊啊啊啊啊") == "啊啊"


def test_stt_filler_two_chars_unchanged():
    """恰好兩個語助詞不需壓縮（已在 threshold 內）。"""
    assert _clean_stt_repeats("嗯嗯") == "嗯嗯"


def test_stt_non_filler_chinese_not_compressed():
    """
    Issue 7 invariant：一般中文重複字不是 STT 噪音，不應壓縮。
    非 filler 的重複字必須原樣保留。
    """
    assert _clean_stt_repeats("想想想") == "想想想"
    assert _clean_stt_repeats("對對對對") == "對對對對"


def test_stt_does_not_compress_digits():
    """
    CLAUDE.md invariant：「純中文數字串（三三三五）仍然會被轉為阿拉伯
    數字（3335）」— 經過 normalize 後應是 3335，不是 33。
    """
    assert normalize("三三三五") == "3335"


# ══════════════════════════════════════════════════════════════
# 空白正規化
# ══════════════════════════════════════════════════════════════

def test_whitespace_multiple_spaces():
    assert normalize("a    b") == "a b"


def test_whitespace_newlines_tabs():
    assert normalize("a\n\tb\r\nc") == "a b c"


def test_whitespace_strip():
    assert normalize("  hello  ") == "hello"


# ══════════════════════════════════════════════════════════════
# Edge cases
# ══════════════════════════════════════════════════════════════

def test_empty_string():
    assert normalize("") == ""


def test_whitespace_only():
    assert normalize("   ") == ""


# ══════════════════════════════════════════════════════════════
# 綜合情境
# ══════════════════════════════════════════════════════════════

def test_composite_dob():
    """民國七十四年五月一日 → 1985年5月1日（demo 實際語料）。"""
    out = normalize("生日是民國七十四年五月一日")
    assert "1985年5月1日" in out


def test_composite_phone_number():
    """零九一二三四五六七八 → 0912345678。"""
    assert "0912345678" in normalize("電話零九一二三四五六七八")


def test_composite_fullwidth_plus_zh_digit():
    """全形數字 → 西元年。"""
    out = normalize("民國１１３年")
    assert "2024年" in out


if __name__ == "__main__":
    import sys
    sys.exit(pytest.main([__file__, "-v"]))

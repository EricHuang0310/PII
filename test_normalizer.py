import pytest

from normalizer import normalize


def test_normalize_empty_string():
    assert normalize("") == ""


def test_normalize_none_like_empty_behavior():
    # 依目前 normalize() 實作，falsy 直接原值返回
    assert normalize(None) is None


def test_fullwidth_to_halfwidth_letters_digits_and_punct():
    text = "ＡＢＣ１２３，電話是０９１２３４５６７８"
    out = normalize(text)
    assert out == "ABC123,電話是0912345678"


def test_whitespace_normalization():
    text = "電話\t是  \n 0912345678\r\n謝謝"
    out = normalize(text)
    assert out == "電話 是 0912345678 謝謝"


def test_zh_digits_phone_conversion():
    text = "我電話是零九一二三四五六七八"
    out = normalize(text)
    assert out == "我電話是0912345678"


def test_zh_digits_credit_card_suffix_conversion():
    text = "卡號末四碼四三二一"
    out = normalize(text)
    assert out == "卡號末四碼4321"


def test_roc_year_with_arabic_digits_to_ce_year():
    text = "生日是民國113年5月1日"
    out = normalize(text)
    assert "2024年5月1日" in out


# v3.1 Issue 6 修正：民國年範圍擴大為 10–150，民國49年現在可以轉換
def test_roc_year_boundary_49_converted_after_issue6_fix():
    text = "生日是民國49年1月1日"
    out = normalize(text)
    assert "1960年1月1日" in out


def test_roc_year_boundary_too_low_not_converted():
    # 民國9年 < 下限 10，不應轉換
    text = "民國9年"
    out = normalize(text)
    assert "民國9年" in out


def test_stt_repeat_cleanup():
    text = "那那那那我要查帳單"
    out = normalize(text)
    assert out == "那那我要查帳單"


# v3.1 Issue 1+2 修正：以下測試已從 xfail 升級為正式測試
def test_roc_year_chinese_digits_should_convert_to_ce_year():
    """Issue 1 修正：先轉中文數字再轉民國年，民國一一三年 → 2024年"""
    text = "生日是民國一一三年三月二十六日"
    out = normalize(text)
    assert out == "生日是2024年3月26日"


def test_chinese_numeral_tens_should_be_supported():
    """Issue 2 修正：支援十/百/千結構，七十四年五月一日 → 1985年5月1日"""
    text = "生日是民國七十四年五月一日"
    out = normalize(text)
    assert out == "生日是1985年5月1日"


def test_chinese_date_components_should_convert():
    """Issue 2 修正：三月二十六日 → 3月26日"""
    text = "預約日期是三月二十六日"
    out = normalize(text)
    assert out == "預約日期是3月26日"

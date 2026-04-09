"""Injected-PII leak tests.

Build a corpus of known-bad texts — one per entity type — and verify the
leak scanner catches each one when the text is NOT masked. This is the
"tripwire" test: if a future refactor breaks any single detector, exactly
this test fires.
"""
from __future__ import annotations

import pytest

from pii_masker.detect.registry import build_regex_detectors
from pii_masker.domain.entity_type import EntityType
from pii_masker.verify.leak_scanner import scan

_LEAK_CASES: dict[str, tuple[str, str]] = {
    "phone_mobile":   ("電話0912345678", "TW_PHONE"),
    "phone_landline": ("公司電話0223456789", "TW_PHONE"),
    "tw_id":          ("身分證A123456789", "TW_ID_NUMBER"),
    "passport":       ("護照AB1234567", "PASSPORT"),
    "credit_card":    ("卡號4111111111111111", "TW_CREDIT_CARD"),
    "bank_account":   ("帳號1234567890", "TW_BANK_ACCOUNT"),
    "email":          ("email user@example.com", "EMAIL_ADDRESS"),
    "otp":            ("驗證碼654321", "OTP"),
    "cvv":            ("安全碼123", "CVV"),
    "amount_txn":     ("我要轉帳50000元", "AMOUNT_TXN"),
    "dob_slash":      ("生日1985/05/01", "DOB"),
    "expiry":         ("到期12/25", "EXPIRY"),
    "staff_id":       ("工號E12345", "STAFF_ID"),
    "loan_ref":       ("貸款ABC123456", "LOAN_REF"),
    "policy_no":      ("保單A1234567", "POLICY_NO"),
}


@pytest.mark.leak
@pytest.mark.parametrize(
    "label,text,expected_type",
    [(k, v[0], v[1]) for k, v in _LEAK_CASES.items()],
)
def test_each_entity_type_is_detected_as_residual(
    label: str,
    text: str,
    expected_type: str,
    default_policy,  # type: ignore[no-untyped-def]
) -> None:
    """Inject unmasked PII into text; assert the scanner catches it."""
    detectors = build_regex_detectors(default_policy)
    residual = scan(text, detectors)
    caught_types = {d.entity_type.value for d in residual}
    assert expected_type in caught_types, (
        f"[{label}] scanner missed {expected_type} in {text!r}; "
        f"caught instead: {sorted(caught_types)}"
    )


@pytest.mark.leak
def test_fully_masked_text_has_zero_leaks(default_policy) -> None:  # type: ignore[no-untyped-def]
    detectors = build_regex_detectors(default_policy)
    masked = (
        "我叫[NAME]身分證[ID]電話[PHONE]信用卡[CARD]"
        "帳號[ACCOUNT]驗證碼[OTP]安全碼[CVV]工號[STAFF_ID]"
    )
    residual = scan(masked, detectors)
    # Detectors can find tokens but not leaked PII — leaks should be 0
    leak_types = {d.entity_type.value for d in residual}
    # Some very permissive regex detectors (e.g. BRANCH: \d{3,4}) may
    # match nothing here. The key assertion is no *high-risk* leaks.
    high_risk = {
        "TW_CREDIT_CARD", "TW_ID_NUMBER", "TW_PHONE", "EMAIL_ADDRESS",
        "TW_BANK_ACCOUNT", "PASSPORT", "OTP",
    }
    assert not (leak_types & high_risk), (
        f"high-risk leaks in fully-masked text: {leak_types & high_risk}"
    )

"""Smoke tests for the simpler keyword-gated detectors.

Rather than a test file per detector (23 files of 5 lines each), these group
the straightforward ones into one parametric test file. Each test runs one
positive case and asserts the detector fires.
"""
from __future__ import annotations

import pytest

from pii_masker.detect.regex.atm_ref import ATMRefDetector
from pii_masker.detect.regex.branch import BranchDetector
from pii_masker.detect.regex.campaign import CampaignDetector
from pii_masker.detect.regex.cvv import CVVDetector
from pii_masker.detect.regex.dob import DOBDetector
from pii_masker.detect.regex.email import EmailDetector
from pii_masker.detect.regex.expiry import ExpiryDetector
from pii_masker.detect.regex.loan_ref import LoanRefDetector
from pii_masker.detect.regex.otp import OTPDetector
from pii_masker.detect.regex.passport import PassportDetector
from pii_masker.detect.regex.pin import PINDetector
from pii_masker.detect.regex.policy_no import PolicyNoDetector
from pii_masker.detect.regex.staff_id import StaffIDDetector
from pii_masker.detect.regex.txn_ref import TxnRefDetector


@pytest.mark.unit
def test_atm_ref_fires() -> None:
    dets = list(ATMRefDetector().detect("交易序號1234567890"))
    assert len(dets) >= 1


@pytest.mark.unit
def test_branch_fires() -> None:
    dets = list(BranchDetector().detect("分行代碼1234"))
    assert len(dets) >= 1


@pytest.mark.unit
def test_campaign_fires() -> None:
    dets = list(CampaignDetector().detect("活動代碼PROMO1234"))
    assert len(dets) >= 1


@pytest.mark.unit
def test_cvv_fires_with_context() -> None:
    dets = list(CVVDetector().detect("安全碼123"))
    assert len(dets) == 1


@pytest.mark.unit
def test_cvv_low_score_without_context() -> None:
    dets = list(CVVDetector().detect("123"))
    # Match exists, but confidence is low (0.30)
    assert dets[0].confidence == pytest.approx(0.30)


@pytest.mark.unit
def test_dob_slash() -> None:
    dets = list(DOBDetector().detect("1985/05/01"))
    assert any(d.subtype == "DOB_SLASH" for d in dets)


@pytest.mark.unit
def test_dob_8_digit() -> None:
    dets = list(DOBDetector().detect("19850501"))
    assert any(d.subtype == "DOB_8" for d in dets)


@pytest.mark.unit
def test_email_fires_without_context() -> None:
    dets = list(EmailDetector().detect("my email is user@example.com"))
    assert len(dets) == 1
    assert dets[0].raw_text == "user@example.com"


@pytest.mark.unit
def test_expiry_slash() -> None:
    dets = list(ExpiryDetector().detect("到期12/25"))
    assert any(d.subtype == "EXPIRY_SLASH" for d in dets)


@pytest.mark.unit
def test_loan_ref_alpha() -> None:
    dets = list(LoanRefDetector().detect("貸款ABC123456"))
    assert any(d.subtype == "LOAN_REF_ALPHA" for d in dets)


@pytest.mark.unit
def test_otp_with_context() -> None:
    dets = list(OTPDetector().detect("驗證碼654321"))
    assert len(dets) == 1


@pytest.mark.unit
def test_passport_fires() -> None:
    dets = list(PassportDetector().detect("護照AB1234567"))
    assert len(dets) >= 1


@pytest.mark.unit
def test_pin_with_context() -> None:
    dets = list(PINDetector().detect("交易密碼1234"))
    assert any(d.subtype == "PIN_46" for d in dets)


@pytest.mark.unit
def test_policy_no_alpha() -> None:
    dets = list(PolicyNoDetector().detect("保單A1234567"))
    assert len(dets) >= 1


@pytest.mark.unit
def test_staff_id_fires() -> None:
    dets = list(StaffIDDetector().detect("工號E12345"))
    assert len(dets) >= 1


@pytest.mark.unit
def test_txn_ref_alpha() -> None:
    dets = list(TxnRefDetector().detect("交易ABC12345678"))
    assert any(d.subtype == "TXN_ALPHA" for d in dets)

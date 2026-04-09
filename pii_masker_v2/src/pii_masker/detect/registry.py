"""Detector registry — builds the full detector list from a MaskingPolicy.

This replaces v3/v4's `recognizers.get_all_custom_recognizers()`. The pipeline
asks this module for "all detectors" once at startup; the resulting list is
passed to `collect_detections()` on every call.
"""
from __future__ import annotations

from pii_masker.detect.address.detector import AddressDetector
from pii_masker.detect.base import BaseDetector
from pii_masker.detect.ner.ckip_adapter import CkipNerAdapter
from pii_masker.detect.regex.amount import AmountDetector
from pii_masker.detect.regex.amount_txn import AmountTxnDetector
from pii_masker.detect.regex.atm_ref import ATMRefDetector
from pii_masker.detect.regex.base import RegexPattern
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
from pii_masker.detect.regex.tw_bank_account import TWBankAccountDetector
from pii_masker.detect.regex.tw_credit_card import TWCreditCardDetector
from pii_masker.detect.regex.tw_id import TWIDDetector
from pii_masker.detect.regex.tw_phone import TWPhoneDetector
from pii_masker.detect.regex.txn_ref import TxnRefDetector
from pii_masker.detect.regex.validators import make_luhn_filter, make_tw_id_filter
from pii_masker.detect.regex.verification_answer import VerificationAnswerDetector
from pii_masker.domain.policy import MaskingPolicy


def _build_amount_detector(policy: MaskingPolicy) -> AmountDetector:
    """AmountDetector needs the high-risk verbs added to its context keywords.

    v3/v4 `config.AMOUNT_CONTEXT` = base amount words + HIGH_RISK_TXN_VERBS.
    """
    from pii_masker.detect.regex import keywords

    class _PolicyAmountDetector(AmountDetector):
        context_keywords = keywords.AMOUNT_BASE + tuple(policy.high_risk_txn_verbs)

    return _PolicyAmountDetector()


def build_regex_detectors(policy: MaskingPolicy) -> list[BaseDetector]:
    """Build all regex + special-case detectors.

    Does NOT include CKIP — that's separated because CKIP needs async warmup
    and is heavy.
    """
    detectors: list[BaseDetector] = [
        TWPhoneDetector(),
        TWIDDetector(
            post_filter=make_tw_id_filter() if policy.strict_validation else None
        ),
        PassportDetector(),
        DOBDetector(),
        TWCreditCardDetector(
            post_filter=make_luhn_filter() if policy.strict_validation else None
        ),
        TWBankAccountDetector(),
        ATMRefDetector(),
        LoanRefDetector(),
        TxnRefDetector(),
        PolicyNoDetector(),
        _build_amount_detector(policy),
        AmountTxnDetector(policy.high_risk_txn_verbs),
        OTPDetector(),
        CVVDetector(),
        ExpiryDetector(),
        PINDetector(),
        AddressDetector(policy.address),
        StaffIDDetector(),
        CampaignDetector(),
        BranchDetector(),
        VerificationAnswerDetector(
            policy.diarization_fallback.answer_window_chars
        ),
        EmailDetector(),
    ]
    return detectors


def build_all_detectors(
    policy: MaskingPolicy,
    *,
    ckip_model: str = "bert-base",
    ckip_device: int = -1,
    include_ckip: bool = True,
) -> list[BaseDetector]:
    """Build the complete detector list used by the pipeline.

    CKIP is NOT warmed up here — call `.warmup()` on the returned adapter
    before the first `detect()` if you want an explicit cold-start.
    """
    detectors = build_regex_detectors(policy)
    if include_ckip:
        detectors.append(CkipNerAdapter(model=ckip_model, device=ckip_device))
    return detectors

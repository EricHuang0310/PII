"""Tests for AmountTxnDetector."""
from __future__ import annotations

import pytest

from pii_masker.detect.regex.amount_txn import AmountTxnDetector, build
from pii_masker.domain.entity_type import EntityType


@pytest.mark.unit
def test_amount_txn_rejects_empty_verbs() -> None:
    with pytest.raises(ValueError, match="at least one verb"):
        AmountTxnDetector([])


@pytest.mark.unit
def test_amount_txn_verb_before_number() -> None:
    det = build(["轉帳", "匯款"])
    dets = list(det.detect("我要轉帳50000元到帳戶"))
    assert len(dets) == 1
    assert dets[0].raw_text == "50000元"
    assert dets[0].entity_type is EntityType.AMOUNT_TXN
    assert dets[0].subtype == "AMOUNT_TXN_VERB"


@pytest.mark.unit
def test_amount_txn_number_before_verb() -> None:
    det = build(["轉帳"])
    dets = list(det.detect("50000元要轉帳"))
    assert len(dets) == 1


@pytest.mark.unit
def test_amount_txn_unrelated_number_not_matched() -> None:
    det = build(["轉帳"])
    # No verb near the number → no match
    assert list(det.detect("我今年35歲")) == []


@pytest.mark.unit
def test_amount_txn_detector_id() -> None:
    det = build(["轉帳"])
    assert det.detector_id == "regex:amount_txn:v1"

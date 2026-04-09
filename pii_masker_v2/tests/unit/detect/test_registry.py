"""Smoke tests for the detector registry (builds full detector list from policy)."""
from __future__ import annotations

import pytest

from pii_masker.detect.registry import build_all_detectors, build_regex_detectors
from pii_masker.domain.entity_type import EntityType


@pytest.mark.unit
def test_registry_builds_all_regex_detectors(default_policy) -> None:  # type: ignore[no-untyped-def]
    detectors = build_regex_detectors(default_policy)
    assert len(detectors) >= 20

    # Every entity type we expect should be covered by at least one detector
    covered: set[EntityType] = set()
    for d in detectors:
        covered |= d.entity_types

    expected = {
        EntityType.TW_PHONE, EntityType.TW_ID_NUMBER, EntityType.PASSPORT,
        EntityType.DOB, EntityType.TW_CREDIT_CARD, EntityType.TW_BANK_ACCOUNT,
        EntityType.ATM_REF, EntityType.LOAN_REF, EntityType.TXN_REF,
        EntityType.POLICY_NO, EntityType.AMOUNT, EntityType.AMOUNT_TXN,
        EntityType.OTP, EntityType.CVV, EntityType.EXPIRY, EntityType.PIN,
        EntityType.STAFF_ID, EntityType.CAMPAIGN, EntityType.BRANCH,
        EntityType.VERIFICATION_ANSWER, EntityType.LOCATION,
        EntityType.EMAIL_ADDRESS,
    }
    missing = expected - covered
    assert not missing, f"Registry missing coverage for {missing}"


@pytest.mark.unit
def test_registry_amount_detector_includes_txn_verbs(default_policy) -> None:  # type: ignore[no-untyped-def]
    detectors = build_regex_detectors(default_policy)
    amount_dets = [d for d in detectors if EntityType.AMOUNT in d.entity_types]
    assert len(amount_dets) == 1
    amount_det = amount_dets[0]
    # Context keywords should include both base amount words and high-risk verbs
    context = amount_det.context_keywords  # type: ignore[attr-defined]
    assert "元" in context
    assert "轉帳" in context


@pytest.mark.unit
def test_registry_build_all_includes_ckip_by_default(default_policy) -> None:  # type: ignore[no-untyped-def]
    dets = build_all_detectors(default_policy)
    detector_ids = [d.detector_id for d in dets]
    assert any(did.startswith("ner:ckip:") for did in detector_ids)


@pytest.mark.unit
def test_registry_build_all_can_exclude_ckip(default_policy) -> None:  # type: ignore[no-untyped-def]
    dets = build_all_detectors(default_policy, include_ckip=False)
    detector_ids = [d.detector_id for d in dets]
    assert not any(did.startswith("ner:ckip:") for did in detector_ids)

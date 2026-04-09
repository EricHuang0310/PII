"""Tests for the three-layer address detector."""
from __future__ import annotations

import pytest

from pii_masker.detect.address.detector import AddressDetector, build
from pii_masker.domain.entity_type import EntityType
from pii_masker.domain.policy import AddressPolicy


@pytest.fixture
def address_policy() -> AddressPolicy:
    return AddressPolicy(
        admin_districts=("台北市", "新北市"),
        chain_landmarks=("Costco", "家樂福"),
    )


@pytest.mark.unit
def test_address_l1_admin_road(address_policy: AddressPolicy) -> None:
    det = build(address_policy)
    dets = list(det.detect("我住在台北市忠孝東路100號"))
    l1 = [d for d in dets if d.subtype == "ADDR_L1_ADMIN"]
    assert len(l1) >= 1
    assert l1[0].entity_type is EntityType.LOCATION
    assert "台北市" in l1[0].raw_text


@pytest.mark.unit
def test_address_l2_chain_landmark(address_policy: AddressPolicy) -> None:
    det = build(address_policy)
    dets = list(det.detect("Costco門市"))
    assert any(d.subtype == "ADDR_L2_CHAIN" for d in dets)


@pytest.mark.unit
def test_address_l3_landmark(address_policy: AddressPolicy) -> None:
    det = build(address_policy)
    dets = list(det.detect("我在文山國小對面"))
    assert any(d.subtype == "ADDR_L3_LANDMARK" for d in dets)


@pytest.mark.unit
def test_address_l3_proximity(address_policy: AddressPolicy) -> None:
    det = build(address_policy)
    dets = list(det.detect("在Costco附近"))
    assert any(d.subtype == "ADDR_L3_PROXIMITY" for d in dets)


@pytest.mark.unit
def test_address_empty_text(address_policy: AddressPolicy) -> None:
    assert build(address_policy).detect("") == ()


@pytest.mark.unit
def test_address_detector_id(address_policy: AddressPolicy) -> None:
    assert build(address_policy).detector_id == "regex:address:v1"

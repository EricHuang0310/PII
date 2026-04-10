"""Tests for EntityType enum."""
from __future__ import annotations

import pytest

from pii_masker.domain.entity_type import EntityType


@pytest.mark.unit
def test_entity_type_is_str_subclass() -> None:
    """EntityType must inherit from str so JSON dumps and dict keys work."""
    assert isinstance(EntityType.PERSON, str)
    assert EntityType.PERSON == "PERSON"


@pytest.mark.unit
def test_entity_type_from_str_happy_path() -> None:
    assert EntityType.from_str("PERSON") is EntityType.PERSON
    assert EntityType.from_str("TW_CREDIT_CARD") is EntityType.TW_CREDIT_CARD


@pytest.mark.unit
def test_entity_type_from_str_unknown_raises() -> None:
    with pytest.raises(ValueError, match="Unknown entity type 'NOT_A_TYPE'"):
        EntityType.from_str("NOT_A_TYPE")


@pytest.mark.unit
def test_entity_type_complete_coverage_of_v3_token_map() -> None:
    """Every key the v3/v4 TOKEN_MAP uses must be in the Enum.

    This test enforces parity with the root config.TOKEN_MAP so golden
    regression tests are meaningful. If someone adds an entity in v3/v4 and
    forgets to add it here, the test fails loud.
    """
    v3_keys = {
        "PERSON", "TW_PHONE", "TW_ID_NUMBER", "PASSPORT", "EMAIL_ADDRESS",
        "LOCATION", "ORG", "DOB", "VERIFICATION_ANSWER", "TW_CREDIT_CARD",
        "TW_BANK_ACCOUNT", "ATM_REF", "TXN_REF", "LOAN_REF", "POLICY_NO",
        "AMOUNT", "AMOUNT_TXN", "OTP", "EXPIRY", "CVV", "PIN", "STAFF_ID",
        "CAMPAIGN", "BRANCH",
    }
    v2_keys = {m.value for m in EntityType}
    missing = v3_keys - v2_keys
    assert not missing, f"EntityType missing v3/v4 entries: {missing}"

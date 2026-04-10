"""EntityType enum — the closed set of PII entity types this pipeline recognizes.

Mirrors the keys of the v3/v4 `config.TOKEN_MAP` one-to-one so that golden parity
against the root `pipeline.py` is byte-exact. Adding a new entity type means:

1. Add a member here
2. Add a detector under `detect/`
3. Add the token mapping in `tokenize/base_tokens.py`
4. Add priority + risk in `policy/defaults.yaml`
"""
from __future__ import annotations

from enum import Enum


class EntityType(str, Enum):
    """Closed set of entity types. Inherits from str for seamless dict keys and JSON."""

    PERSON = "PERSON"
    TW_PHONE = "TW_PHONE"
    TW_ID_NUMBER = "TW_ID_NUMBER"
    PASSPORT = "PASSPORT"
    EMAIL_ADDRESS = "EMAIL_ADDRESS"
    LOCATION = "LOCATION"
    ORG = "ORG"
    DOB = "DOB"
    VERIFICATION_ANSWER = "VERIFICATION_ANSWER"
    TW_CREDIT_CARD = "TW_CREDIT_CARD"
    TW_BANK_ACCOUNT = "TW_BANK_ACCOUNT"
    ATM_REF = "ATM_REF"
    TXN_REF = "TXN_REF"
    LOAN_REF = "LOAN_REF"
    POLICY_NO = "POLICY_NO"
    AMOUNT = "AMOUNT"
    AMOUNT_TXN = "AMOUNT_TXN"
    OTP = "OTP"
    EXPIRY = "EXPIRY"
    CVV = "CVV"
    PIN = "PIN"
    STAFF_ID = "STAFF_ID"
    CAMPAIGN = "CAMPAIGN"
    BRANCH = "BRANCH"

    @classmethod
    def from_str(cls, name: str) -> EntityType:
        """Parse a string into an EntityType, raising ValueError with a helpful message."""
        try:
            return cls(name)
        except ValueError as e:
            valid = ", ".join(m.value for m in cls)
            raise ValueError(
                f"Unknown entity type {name!r}. Valid types: {valid}"
            ) from e

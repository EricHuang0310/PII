"""Taiwanese bank account detector (TW_BANK_ACCOUNT)."""
from __future__ import annotations

from pii_masker.detect.regex import keywords
from pii_masker.detect.regex.base import RegexDetector, RegexPattern
from pii_masker.domain.entity_type import EntityType


class TWBankAccountDetector(RegexDetector):
    entity_type = EntityType.TW_BANK_ACCOUNT
    # Negative lookahead prevents mobile numbers (09XXXXXXXX) from matching
    patterns = (RegexPattern.compile("BANK_ACCT", r"(?!09\d{8})\d{10,14}", 0.50),)
    context_keywords = keywords.BANK_ACCOUNT
    version = "v1"

"""Taiwanese credit card detector (TW_CREDIT_CARD).

Ports v3/v4 TWCreditCardRecognizer with an OPTIONAL Luhn validator.
"""
from __future__ import annotations

from pii_masker.detect.regex import keywords
from pii_masker.detect.regex.base import RegexDetector, RegexPattern
from pii_masker.detect.regex.validators import make_luhn_filter
from pii_masker.domain.entity_type import EntityType


class TWCreditCardDetector(RegexDetector):
    entity_type = EntityType.TW_CREDIT_CARD
    patterns = (RegexPattern.compile("CC_16", r"\d{16}", 0.55),)
    context_keywords = keywords.CREDIT_CARD
    version = "v1"


def build(strict: bool = False) -> TWCreditCardDetector:
    if strict:
        return TWCreditCardDetector(post_filter=make_luhn_filter())
    return TWCreditCardDetector()

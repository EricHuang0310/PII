"""Plain AMOUNT detector (conditional masking applied later).

This detector ONLY detects numeric/currency patterns. Whether to mask them
depends on proximity to an account/card — that decision is made in
`rules/conditional_amount.py`.
"""
from __future__ import annotations

from pii_masker.detect.regex import keywords
from pii_masker.detect.regex.base import RegexDetector, RegexPattern
from pii_masker.domain.entity_type import EntityType


class AmountDetector(RegexDetector):
    entity_type = EntityType.AMOUNT
    patterns = (
        RegexPattern.compile("AMOUNT_YUAN", r"\d+(?:,\d{3})*元",        0.80),
        RegexPattern.compile("AMOUNT_KUAI", r"\d+(?:,\d{3})*塊",        0.75),
        RegexPattern.compile("AMOUNT_NT",   r"NT\$?\s*\d+(?:,\d{3})*", 0.80),
        RegexPattern.compile("AMOUNT_NUM",  r"\d+(?:,\d{3})*",          0.40),
    )
    # Context includes both the base amount words AND the high-risk verbs.
    # The v3/v4 pipeline mirrors this by concatenating the two lists.
    context_keywords = keywords.AMOUNT_BASE  # verbs are added by factory
    version = "v1"

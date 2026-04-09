"""Taiwanese phone number detector (TW_PHONE).

Ports v3/v4 TWPhoneRecognizer:
- MOBILE:   09 + 8 digits       (score 0.85)
- LANDLINE: 0[2-8] + 7..8 digits (score 0.75)
"""
from __future__ import annotations

from pii_masker.detect.regex import keywords
from pii_masker.detect.regex.base import RegexDetector, RegexPattern
from pii_masker.domain.entity_type import EntityType


class TWPhoneDetector(RegexDetector):
    entity_type = EntityType.TW_PHONE
    patterns = (
        RegexPattern.compile("MOBILE",   r"09\d{8}",       0.85),
        RegexPattern.compile("LANDLINE", r"0[2-8]\d{7,8}", 0.75),
    )
    context_keywords = keywords.PHONE
    version = "v1"

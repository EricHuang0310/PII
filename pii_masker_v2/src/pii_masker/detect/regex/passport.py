"""Passport number detector (PASSPORT)."""
from __future__ import annotations

from pii_masker.detect.regex import keywords
from pii_masker.detect.regex.base import RegexDetector, RegexPattern
from pii_masker.domain.entity_type import EntityType


class PassportDetector(RegexDetector):
    entity_type = EntityType.PASSPORT
    patterns = (RegexPattern.compile("PASSPORT", r"[A-Z]{1,2}\d{7,9}", 0.70),)
    context_keywords = keywords.PASSPORT
    version = "v1"

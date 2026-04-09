"""PIN detector (PIN)."""
from __future__ import annotations

from pii_masker.detect.regex import keywords
from pii_masker.detect.regex.base import RegexDetector, RegexPattern
from pii_masker.domain.entity_type import EntityType


class PINDetector(RegexDetector):
    entity_type = EntityType.PIN
    patterns = (RegexPattern.compile("PIN_46", r"\d{4,6}", 0.30),)
    context_keywords = keywords.PIN
    version = "v1"

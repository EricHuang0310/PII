"""Date of birth detector (DOB)."""
from __future__ import annotations

from pii_masker.detect.regex import keywords
from pii_masker.detect.regex.base import RegexDetector, RegexPattern
from pii_masker.domain.entity_type import EntityType


class DOBDetector(RegexDetector):
    entity_type = EntityType.DOB
    patterns = (
        RegexPattern.compile("DOB_8",     r"\d{8}",                    0.50),
        RegexPattern.compile("DOB_SLASH", r"\d{4}[/-]\d{2}[/-]\d{2}", 0.70),
    )
    context_keywords = keywords.DOB
    version = "v1"

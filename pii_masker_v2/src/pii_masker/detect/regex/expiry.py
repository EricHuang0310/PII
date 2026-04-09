"""Credit card expiry detector (EXPIRY)."""
from __future__ import annotations

from pii_masker.detect.regex import keywords
from pii_masker.detect.regex.base import RegexDetector, RegexPattern
from pii_masker.domain.entity_type import EntityType


class ExpiryDetector(RegexDetector):
    entity_type = EntityType.EXPIRY
    patterns = (
        RegexPattern.compile("EXPIRY_MMYY",  r"(?:0[1-9]|1[0-2])\d{2}",  0.45),
        RegexPattern.compile("EXPIRY_SLASH", r"(?:0[1-9]|1[0-2])/\d{2}", 0.65),
    )
    context_keywords = keywords.EXPIRY
    version = "v1"

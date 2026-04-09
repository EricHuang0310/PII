"""Staff ID detector (STAFF_ID)."""
from __future__ import annotations

from pii_masker.detect.regex import keywords
from pii_masker.detect.regex.base import RegexDetector, RegexPattern
from pii_masker.domain.entity_type import EntityType


class StaffIDDetector(RegexDetector):
    entity_type = EntityType.STAFF_ID
    patterns = (
        RegexPattern.compile("STAFF_ALPHA",  r"[A-Z]\d{4,8}",             0.55),
        RegexPattern.compile("STAFF_PREFIX", r"(?:EMP|STAFF|E|A)\d{4,8}", 0.70),
    )
    context_keywords = keywords.STAFF_ID
    version = "v1"

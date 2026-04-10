"""Insurance policy number detector (POLICY_NO)."""
from __future__ import annotations

from pii_masker.detect.regex import keywords
from pii_masker.detect.regex.base import RegexDetector, RegexPattern
from pii_masker.domain.entity_type import EntityType


class PolicyNoDetector(RegexDetector):
    entity_type = EntityType.POLICY_NO
    patterns = (
        RegexPattern.compile("POLICY_ALPHA", r"[A-Z]\d{6,12}", 0.60),
        RegexPattern.compile("POLICY_NUM",   r"P\d{6,10}",     0.75),
    )
    context_keywords = keywords.POLICY
    version = "v1"

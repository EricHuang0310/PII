"""ATM reference detector (ATM_REF)."""
from __future__ import annotations

from pii_masker.detect.regex import keywords
from pii_masker.detect.regex.base import RegexDetector, RegexPattern
from pii_masker.domain.entity_type import EntityType


class ATMRefDetector(RegexDetector):
    entity_type = EntityType.ATM_REF
    patterns = (RegexPattern.compile("ATM_REF", r"\d{8,20}", 0.40),)
    context_keywords = keywords.ATM
    version = "v1"

"""Transaction reference detector (TXN_REF)."""
from __future__ import annotations

from pii_masker.detect.regex import keywords
from pii_masker.detect.regex.base import RegexDetector, RegexPattern
from pii_masker.domain.entity_type import EntityType


class TxnRefDetector(RegexDetector):
    entity_type = EntityType.TXN_REF
    patterns = (
        RegexPattern.compile("TXN_NUM",   r"\d{8,20}",            0.40),
        RegexPattern.compile("TXN_ALPHA", r"[A-Z]{1,3}\d{8,15}",  0.60),
    )
    context_keywords = keywords.TXN
    version = "v1"

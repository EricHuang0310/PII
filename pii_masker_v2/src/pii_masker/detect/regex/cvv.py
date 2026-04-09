"""CVV detector (CVV).

Keyword-gated: a bare 3-digit number has a very low base score, so without
nearby CVV/安全碼/末三碼 context the detection drops below the pipeline's
score threshold. This preserves v3/v4 behavior.
"""
from __future__ import annotations

from pii_masker.detect.regex import keywords
from pii_masker.detect.regex.base import RegexDetector, RegexPattern
from pii_masker.domain.entity_type import EntityType


class CVVDetector(RegexDetector):
    entity_type = EntityType.CVV
    patterns = (RegexPattern.compile("CVV_3", r"\d{3}", 0.30),)
    context_keywords = keywords.CVV
    version = "v1"

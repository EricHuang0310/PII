"""Branch code detector (BRANCH)."""
from __future__ import annotations

from pii_masker.detect.regex import keywords
from pii_masker.detect.regex.base import RegexDetector, RegexPattern
from pii_masker.domain.entity_type import EntityType


class BranchDetector(RegexDetector):
    entity_type = EntityType.BRANCH
    patterns = (
        RegexPattern.compile("BRANCH_NUM",   r"\d{3,4}",           0.35),
        RegexPattern.compile("BRANCH_ALPHA", r"[A-Z]{2,4}\d{2,4}", 0.55),
    )
    context_keywords = keywords.BRANCH
    version = "v1"

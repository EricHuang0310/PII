"""Loan reference detector (LOAN_REF)."""
from __future__ import annotations

from pii_masker.detect.regex import keywords
from pii_masker.detect.regex.base import RegexDetector, RegexPattern
from pii_masker.domain.entity_type import EntityType


class LoanRefDetector(RegexDetector):
    entity_type = EntityType.LOAN_REF
    patterns = (
        RegexPattern.compile("LOAN_REF_NUM",   r"\d{8,15}",          0.45),
        RegexPattern.compile("LOAN_REF_ALPHA", r"[A-Z]{1,3}\d{6,12}", 0.65),
    )
    context_keywords = keywords.LOAN
    version = "v1"

"""Email address detector (EMAIL_ADDRESS).

v3/v4 relied on Presidio's built-in EmailRecognizer; here we ship a standalone
regex so the pipeline doesn't need Presidio. Pattern is intentionally
conservative — RFC 5322 is a bottomless pit.
"""
from __future__ import annotations

from pii_masker.detect.regex.base import RegexDetector, RegexPattern
from pii_masker.domain.entity_type import EntityType


class EmailDetector(RegexDetector):
    entity_type = EntityType.EMAIL_ADDRESS
    patterns = (
        RegexPattern.compile(
            "EMAIL",
            r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}",
            0.90,
        ),
    )
    context_keywords = ()  # self-evident format, no context needed
    version = "v1"

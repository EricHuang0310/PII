"""Taiwanese national ID detector (TW_ID_NUMBER).

Ports v3/v4 TWIDRecognizer with an OPTIONAL checksum validator. The validator
is attached by `build_all_detectors()` when `policy.strict_validation` is True.
"""
from __future__ import annotations

from pii_masker.detect.regex import keywords
from pii_masker.detect.regex.base import RegexDetector, RegexPattern
from pii_masker.detect.regex.validators import make_tw_id_filter
from pii_masker.domain.entity_type import EntityType


class TWIDDetector(RegexDetector):
    entity_type = EntityType.TW_ID_NUMBER
    patterns = (RegexPattern.compile("TW_ID", r"[A-Za-z][12]\d{8}", 0.90),)
    context_keywords = keywords.ID_NUMBER
    version = "v1"


def build(strict: bool = False) -> TWIDDetector:
    """Build a TW ID detector, optionally with checksum validation."""
    if strict:
        return TWIDDetector(post_filter=make_tw_id_filter())
    return TWIDDetector()

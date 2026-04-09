"""OTP detector (OTP)."""
from __future__ import annotations

from pii_masker.detect.regex import keywords
from pii_masker.detect.regex.base import RegexDetector, RegexPattern
from pii_masker.domain.entity_type import EntityType


class OTPDetector(RegexDetector):
    entity_type = EntityType.OTP
    patterns = (RegexPattern.compile("OTP_6", r"\d{6}", 0.50),)
    context_keywords = keywords.OTP
    version = "v1"

"""Marketing campaign code detector (CAMPAIGN)."""
from __future__ import annotations

from pii_masker.detect.regex import keywords
from pii_masker.detect.regex.base import RegexDetector, RegexPattern
from pii_masker.domain.entity_type import EntityType


class CampaignDetector(RegexDetector):
    entity_type = EntityType.CAMPAIGN
    patterns = (RegexPattern.compile("CAMPAIGN_CODE", r"[A-Z]{2,4}\d{3,6}", 0.50),)
    context_keywords = keywords.CAMPAIGN
    version = "v1"

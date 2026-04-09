"""Three-layer Chinese address detector (LOCATION).

Ports v3/v4 `AddressEnhancedRecognizer`:

- L1 ADMIN:     administrative district + road/lane/number (高信心)
- L2 CHAIN:     chain landmarks (Costco / 家樂福 / SOGO / ...)
- L3 LANDMARK:  generic landmark suffixes (國小 / 捷運站 / 夜市 / ...)
- L3 PROXIMITY: "X附近 / 旁邊 / 對面" expressions

Uses the admin_districts and chain_landmarks lists from the MaskingPolicy so
the dictionaries can be overridden per deployment.
"""
from __future__ import annotations

import re
from collections.abc import Sequence
from typing import Pattern

from pii_masker.detect.base import BaseDetector
from pii_masker.domain.detection import Detection
from pii_masker.domain.entity_type import EntityType
from pii_masker.domain.policy import AddressPolicy
from pii_masker.domain.span import Span

# v3/v4 LANDMARK_SUFFIX_PATTERN — mostly static, not policy-driven
_LANDMARK_SUFFIX_PATTERN: str = (
    r"[\u4e00-\u9fff]{2,6}"
    r"(?:國小|國中|高中|大學|醫院|診所|公園|廟|宮|"
    r"捷運站|火車站|高鐵站|客運站|機場|"
    r"夜市|市場|商圈|購物中心|廣場)"
)

_PROXIMITY_SUFFIX_GROUP: str = r"(?:附近|旁邊|對面|隔壁|那邊|這邊|一帶)"

_L1_TEMPLATE: str = (
    "{admin}"
    r"[\u4e00-\u9fff]{{0,15}}?"
    r"(?:路|街|大道)"
    r"(?:[\u4e00-\u9fff]?段)?"
    r"(?:\d{{1,4}}巷)?"
    r"(?:\d{{1,4}}弄)?"
    r"(?:\d{{1,4}}號)?"
    r"(?:\d{{1,3}}樓)?"
    r"(?:之\d{{1,3}})?"
)


def _build_l1(admin_districts: Sequence[str]) -> Pattern[str]:
    admin_alt = "(?:" + "|".join(re.escape(d) for d in admin_districts) + ")"
    return re.compile(_L1_TEMPLATE.format(admin=admin_alt))


def _build_l2(chain_landmarks: Sequence[str]) -> Pattern[str]:
    chain_alt = "(?:" + "|".join(re.escape(c) for c in chain_landmarks) + ")"
    return re.compile(chain_alt + r".{0,4}(?:店|門市|分店|賣場)?")


def _build_proximity(
    admin_districts: Sequence[str], chain_landmarks: Sequence[str]
) -> Pattern[str]:
    all_anchors = list(chain_landmarks) + list(admin_districts)
    anchor_alt = "(?:" + "|".join(re.escape(a) for a in all_anchors) + ")"
    return re.compile(
        anchor_alt + r"[\u4e00-\u9fff]{0,8}" + _PROXIMITY_SUFFIX_GROUP
    )


class AddressDetector(BaseDetector):
    """Three-layer address detector, built from an AddressPolicy."""

    _VERSION: str = "v1"

    def __init__(self, address_policy: AddressPolicy) -> None:
        self._l1: Pattern[str] = _build_l1(address_policy.admin_districts)
        self._l2: Pattern[str] = _build_l2(address_policy.chain_landmarks)
        self._l3_landmark: Pattern[str] = re.compile(_LANDMARK_SUFFIX_PATTERN)
        self._l3_proximity: Pattern[str] = _build_proximity(
            address_policy.admin_districts, address_policy.chain_landmarks
        )

    @property
    def detector_id(self) -> str:
        return f"regex:address:{self._VERSION}"

    @property
    def entity_types(self) -> frozenset[EntityType]:
        return frozenset({EntityType.LOCATION})

    def detect(self, text: str) -> Sequence[Detection]:
        if not text:
            return ()
        results: list[Detection] = []
        for layer, pattern, score in (
            ("ADDR_L1_ADMIN",     self._l1,           0.85),
            ("ADDR_L2_CHAIN",     self._l2,           0.75),
            ("ADDR_L3_LANDMARK",  self._l3_landmark,  0.70),
            ("ADDR_L3_PROXIMITY", self._l3_proximity, 0.72),
        ):
            for m in pattern.finditer(text):
                results.append(
                    Detection(
                        span=Span(m.start(), m.end()),
                        entity_type=EntityType.LOCATION,
                        confidence=score,
                        detector_id=self.detector_id,
                        subtype=layer,
                        raw_text=m.group(0),
                    )
                )
        return results


def build(address_policy: AddressPolicy) -> AddressDetector:
    return AddressDetector(address_policy)

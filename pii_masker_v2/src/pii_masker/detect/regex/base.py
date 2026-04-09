"""Shared base for regex-based detectors.

Ports the behavior of Presidio's `PatternRecognizer` that the v3/v4 pipeline
relied on:

1. A list of named patterns, each with a base confidence score
2. A keyword context list — if any keyword appears within `context_window`
   characters of a match, boost the score by `context_boost`
3. A minimum score threshold applied before returning

The implementation is intentionally standalone (no Presidio import) so the
v2 package can run without Presidio installed.
"""
from __future__ import annotations

import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from typing import Callable, Pattern

from pii_masker.detect.base import BaseDetector
from pii_masker.domain.detection import Detection
from pii_masker.domain.entity_type import EntityType
from pii_masker.domain.span import Span

# Default context settings — mirror Presidio defaults used by v3/v4.
DEFAULT_CONTEXT_WINDOW: int = 20
DEFAULT_CONTEXT_BOOST: float = 0.35


@dataclass(frozen=True, slots=True)
class RegexPattern:
    """One named regex pattern with a base confidence score."""

    name: str
    regex: Pattern[str]
    base_score: float

    @classmethod
    def compile(cls, name: str, pattern: str, base_score: float) -> RegexPattern:
        return cls(name=name, regex=re.compile(pattern), base_score=base_score)


class RegexDetector(BaseDetector):
    """Generic regex detector with keyword context scoring.

    Subclasses set `entity_type`, `patterns`, `context_keywords`, and
    `version`. Construction compiles the context keyword union into a single
    regex for fast lookup.

    `post_filter` is an optional callable that receives a candidate Detection
    and its raw text; returning False drops the candidate. Used by detectors
    that need a second-stage validator (Luhn, TW ID checksum, etc.).
    """

    entity_type: EntityType = EntityType.PERSON  # overridden
    patterns: tuple[RegexPattern, ...] = ()
    context_keywords: tuple[str, ...] = ()
    context_window: int = DEFAULT_CONTEXT_WINDOW
    context_boost: float = DEFAULT_CONTEXT_BOOST
    min_score: float = 0.0
    version: str = "v1"

    def __init__(
        self,
        *,
        post_filter: Callable[[Detection, str], bool] | None = None,
    ) -> None:
        if not self.patterns:
            raise ValueError(
                f"{type(self).__name__} must define at least one pattern"
            )
        self._context_re: Pattern[str] | None = (
            re.compile("|".join(re.escape(k) for k in self.context_keywords))
            if self.context_keywords
            else None
        )
        self._post_filter = post_filter

    @property
    def detector_id(self) -> str:
        return f"regex:{self.entity_type.value.lower()}:{self.version}"

    @property
    def entity_types(self) -> frozenset[EntityType]:
        return frozenset({self.entity_type})

    def detect(self, text: str) -> Sequence[Detection]:
        if not text:
            return ()
        results: list[Detection] = []
        for pattern in self.patterns:
            for m in pattern.regex.finditer(text):
                start, end = m.start(), m.end()
                raw = text[start:end]
                score = pattern.base_score
                if self._has_context(text, start, end):
                    score = min(1.0, score + self.context_boost)
                if score < self.min_score:
                    continue
                candidate = Detection(
                    span=Span(start, end),
                    entity_type=self.entity_type,
                    confidence=score,
                    detector_id=self.detector_id,
                    subtype=pattern.name,
                    raw_text=raw,
                )
                if self._post_filter is not None and not self._post_filter(
                    candidate, text
                ):
                    continue
                results.append(candidate)
        return results

    def _has_context(self, text: str, start: int, end: int) -> bool:
        if self._context_re is None:
            return False
        window_start = max(0, start - self.context_window)
        window_end = min(len(text), end + self.context_window)
        window = text[window_start:window_end]
        return self._context_re.search(window) is not None


def collect_detections(
    detectors: Iterable[BaseDetector],
    text: str,
) -> list[Detection]:
    """Run every detector over `text` and concatenate the results.

    Order within the output is detector-by-detector in iteration order, then
    whatever order each detector returned internally. Callers must sort or
    resolve as needed.
    """
    out: list[Detection] = []
    for d in detectors:
        out.extend(d.detect(text))
    return out

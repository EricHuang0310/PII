"""Detector Protocol — the port that every detection adapter implements.

The core pipeline depends ONLY on this protocol. Adapters (regex, CKIP NER,
address, Presidio bridge) live on the outside. Swapping a detector is one
file; the pipeline never needs to change.
"""
from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol, runtime_checkable

from pii_masker.domain.detection import Detection
from pii_masker.domain.entity_type import EntityType


@runtime_checkable
class Detector(Protocol):
    """One detection strategy. Pure by contract — must not mutate input text."""

    @property
    def detector_id(self) -> str:
        """Stable identifier, e.g. 'regex:tw_phone:v1' or 'ner:ckip:bert-base:v1'."""
        ...

    @property
    def entity_types(self) -> frozenset[EntityType]:
        """The set of entity types this detector produces."""
        ...

    def detect(self, text: str) -> Sequence[Detection]:
        """Return all detections found in `text`.

        Contract:
        - Must not mutate `text`
        - Must not raise on empty text (return empty sequence)
        - Every returned Detection has confidence in [0, 1]
        - Every returned Detection.span refers to `text` indices
        - Return order is not specified — callers must not rely on it
        """
        ...

    def detect_batch(self, texts: Sequence[str]) -> list[list[Detection]]:
        """Optional batch API.

        Default implementation falls back to per-text `detect()`. NER detectors
        should override this to exploit GPU batching. The return value is a
        list-of-lists — one sublist per input text, in the same order.
        """
        ...


class BaseDetector:
    """Concrete base class providing the default batch fallback.

    Subclasses that cannot benefit from batching (regex-based detectors) can
    inherit from this directly and only implement `detect()`.
    """

    @property
    def detector_id(self) -> str:  # pragma: no cover - overridden
        raise NotImplementedError

    @property
    def entity_types(self) -> frozenset[EntityType]:  # pragma: no cover
        raise NotImplementedError

    def detect(self, text: str) -> Sequence[Detection]:  # pragma: no cover
        raise NotImplementedError

    def detect_batch(self, texts: Sequence[str]) -> list[list[Detection]]:
        """Default batch implementation: call detect() for each text."""
        return [list(self.detect(t)) for t in texts]

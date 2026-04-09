"""CKIP Transformers NER adapter — PERSON / LOCATION / ORG for Traditional Chinese.

This is the v2 equivalent of the root `ckip_recognizer.py`. Key differences:

- Explicit `warmup()` method so cold-start latency is opt-in, not a surprise
  on the first `mask()` call
- `detect_batch()` uses CKIP's native batch API so N turns take ONE model call
- Emits frozen `Detection` objects with stable UUIDs (not Presidio
  RecognizerResult)
- Import of `ckip_transformers` is deferred until `warmup()` / `detect()` is
  called, so the pipeline can be imported and tested without the package
  installed (tests that actually need the model use
  `@pytest.mark.requires_ckip` + skipif).
"""
from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from pii_masker.detect.base import BaseDetector
from pii_masker.domain.detection import Detection
from pii_masker.domain.entity_type import EntityType
from pii_masker.domain.errors import DetectorError
from pii_masker.domain.span import Span

# CKIP NER label → our EntityType enum.
# The root `ckip_recognizer.py` maps 機構名稱 → ORG in v4; preserved here.
_LABEL_MAP: dict[str, EntityType] = {
    "PERSON":       EntityType.PERSON,
    "人名":          EntityType.PERSON,
    "GPE":          EntityType.LOCATION,
    "LOC":          EntityType.LOCATION,
    "地緣政治實體":  EntityType.LOCATION,
    "位置":          EntityType.LOCATION,
    "ORG":          EntityType.ORG,
    "機構名稱":      EntityType.ORG,
    "ORGANIZATION": EntityType.ORG,
    "FAC":          EntityType.LOCATION,
    "建築物":        EntityType.LOCATION,
}

_DEFAULT_CONFIDENCE: float = 0.90
_SUPPORTED_ENTITIES: frozenset[EntityType] = frozenset(
    {EntityType.PERSON, EntityType.LOCATION, EntityType.ORG}
)


class CkipNerAdapter(BaseDetector):
    """Adapter wrapping ckip-transformers' NER driver."""

    def __init__(
        self,
        *,
        model: str = "bert-base",
        device: int = -1,
        confidence: float = _DEFAULT_CONFIDENCE,
    ) -> None:
        if not 0.0 <= confidence <= 1.0:
            raise ValueError("confidence must be in [0, 1]")
        self._model_name: str = model
        self._device: int = device
        self._confidence: float = confidence
        self._ner_driver: Any | None = None  # lazy — set in warmup()

    @property
    def detector_id(self) -> str:
        return f"ner:ckip:{self._model_name}:v1"

    @property
    def entity_types(self) -> frozenset[EntityType]:
        return _SUPPORTED_ENTITIES

    @property
    def is_warmed_up(self) -> bool:
        return self._ner_driver is not None

    def warmup(self) -> None:
        """Eagerly load the CKIP NER driver.

        Safe to call multiple times — no-op if already loaded. Raises
        `DetectorError` if `ckip-transformers` is not installed.
        """
        if self._ner_driver is not None:
            return
        try:
            from ckip_transformers.nlp import CkipNerChunker  # type: ignore[import-not-found]
        except ImportError as e:
            raise DetectorError(
                "ckip-transformers is required for CkipNerAdapter. "
                "Install with: pip install ckip-transformers torch"
            ) from e
        try:
            self._ner_driver = CkipNerChunker(
                model=self._model_name, device=self._device
            )
        except Exception as e:  # pragma: no cover - model load failures
            raise DetectorError(
                f"Failed to load CKIP NER model {self._model_name!r}: {e}"
            ) from e

    def detect(self, text: str) -> Sequence[Detection]:
        if not text:
            return ()
        if self._ner_driver is None:
            self.warmup()
        assert self._ner_driver is not None  # for mypy
        ner_results = self._ner_driver([text])
        return _convert_ner_results(ner_results[0], self.detector_id, self._confidence)

    def detect_batch(self, texts: Sequence[str]) -> list[list[Detection]]:
        """Exploit CKIP's batch inference — one model call for N texts."""
        if not texts:
            return []
        if self._ner_driver is None:
            self.warmup()
        assert self._ner_driver is not None
        # Empty strings confuse some CKIP versions — handle them out-of-band.
        batch_inputs: list[str] = []
        batch_indices: list[int] = []
        out: list[list[Detection]] = [[] for _ in texts]
        for i, t in enumerate(texts):
            if t:
                batch_inputs.append(t)
                batch_indices.append(i)
        if batch_inputs:
            batch_results = self._ner_driver(batch_inputs)
            for src_idx, raw in zip(batch_indices, batch_results):
                out[src_idx] = list(
                    _convert_ner_results(raw, self.detector_id, self._confidence)
                )
        return out


def _convert_ner_results(
    entities: Any, detector_id: str, confidence: float
) -> Sequence[Detection]:
    """Convert a CKIP NER result list into frozen Detection objects.

    CKIP yields objects with `.word`, `.ner`, `.idx` (start, end) attributes.
    Labels not in `_LABEL_MAP` are dropped silently.
    """
    out: list[Detection] = []
    for ent in entities:
        label = getattr(ent, "ner", None)
        if label is None:
            continue
        entity_type = _LABEL_MAP.get(label)
        if entity_type is None:
            continue
        # CKIP `idx` is (start, end) — end is exclusive like Python slicing
        idx = getattr(ent, "idx", None)
        if idx is None or len(idx) != 2:
            continue
        start, end = int(idx[0]), int(idx[1])
        raw = getattr(ent, "word", "")
        out.append(
            Detection(
                span=Span(start, end),
                entity_type=entity_type,
                confidence=confidence,
                detector_id=detector_id,
                subtype=str(label),
                raw_text=raw,
            )
        )
    return out

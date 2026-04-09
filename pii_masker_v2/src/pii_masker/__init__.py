"""pii_masker v2 — Taiwanese-bank voice/STT PII masking pipeline (rewrite).

Public API re-exports. Internal imports should prefer the fully-qualified module paths.
"""
from __future__ import annotations

__version__ = "2.0.0"

from pii_masker.domain.detection import Detection
from pii_masker.domain.dialogue import DialogueTurn, Speaker
from pii_masker.domain.entity_type import EntityType
from pii_masker.domain.errors import DetectorError, PIILeakError, PolicyError
from pii_masker.domain.policy import MaskingPolicy
from pii_masker.domain.result import ConflictEntry, MaskingResult
from pii_masker.domain.span import Span
from pii_masker.usability.tags import UsabilityTag

# Keep the top-level namespace narrow — orchestration functions are defined late
# in the build (Phase G) and imported lazily from pii_masker.pipeline.

__all__ = [
    "__version__",
    "ConflictEntry",
    "Detection",
    "DetectorError",
    "DialogueTurn",
    "EntityType",
    "MaskingPolicy",
    "MaskingResult",
    "PIILeakError",
    "PolicyError",
    "Span",
    "Speaker",
    "UsabilityTag",
]

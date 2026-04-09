"""Domain-level errors.

These live in `domain/` so any layer can raise them without creating cycles.
"""
from __future__ import annotations


class PIIMaskerError(Exception):
    """Base class for all pii_masker exceptions."""


class PolicyError(PIIMaskerError):
    """Raised when a MaskingPolicy is malformed, incomplete, or fails validation."""


class DetectorError(PIIMaskerError):
    """Raised when a detector adapter fails to initialize or run.

    Example: CKIP model cannot be loaded, regex fails to compile, Presidio
    registry misconfigured.
    """


class PIILeakError(PIIMaskerError):
    """Raised by Step 7 (leak scanner) when residual PII is found in `masked_text`.

    Fail-closed contract: every `mask()` call either returns a `MaskingResult`
    that has passed leak scanning, or raises this error. There is no silent
    passthrough. Catching and continuing is explicitly discouraged — surface it
    to the operator.
    """

    def __init__(
        self,
        message: str,
        residual_spans: tuple[tuple[int, int, str], ...] = (),
    ) -> None:
        super().__init__(message)
        self.residual_spans = residual_spans

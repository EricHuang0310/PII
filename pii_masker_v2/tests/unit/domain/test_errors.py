"""Tests for domain errors."""
from __future__ import annotations

import pytest

from pii_masker.domain.errors import (
    DetectorError,
    PIILeakError,
    PIIMaskerError,
    PolicyError,
)


@pytest.mark.unit
def test_error_hierarchy() -> None:
    assert issubclass(PolicyError, PIIMaskerError)
    assert issubclass(DetectorError, PIIMaskerError)
    assert issubclass(PIILeakError, PIIMaskerError)


@pytest.mark.unit
def test_pii_leak_error_carries_residual_spans() -> None:
    err = PIILeakError(
        "residual PII detected in masked_text",
        residual_spans=((0, 10, "TW_CREDIT_CARD"),),
    )
    assert err.residual_spans == ((0, 10, "TW_CREDIT_CARD"),)


@pytest.mark.unit
def test_pii_leak_error_default_residual_spans_empty() -> None:
    err = PIILeakError("no detail")
    assert err.residual_spans == ()

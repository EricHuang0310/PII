"""Tests for NFC normalization."""
from __future__ import annotations

import pytest

from pii_masker.normalize.nfc import to_nfc


@pytest.mark.unit
def test_nfc_empty() -> None:
    assert to_nfc("") == ""


@pytest.mark.unit
def test_nfc_noop_on_already_normalized_text() -> None:
    assert to_nfc("hello") == "hello"
    assert to_nfc("王小明") == "王小明"


@pytest.mark.unit
def test_nfc_composes_decomposed_accents() -> None:
    # "é" = U+00E9 vs "e" + U+0301 combining acute
    decomposed = "e\u0301"
    composed = to_nfc(decomposed)
    assert composed == "\u00e9"
    assert len(composed) == 1

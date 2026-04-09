"""Tests for whitespace normalization."""
from __future__ import annotations

import pytest

from pii_masker.normalize.whitespace import normalize_whitespace


@pytest.mark.unit
def test_whitespace_empty() -> None:
    assert normalize_whitespace("") == ""


@pytest.mark.unit
def test_whitespace_collapses_runs() -> None:
    assert normalize_whitespace("a   b") == "a b"


@pytest.mark.unit
def test_whitespace_trims() -> None:
    assert normalize_whitespace("  hello  ") == "hello"


@pytest.mark.unit
def test_whitespace_converts_newlines() -> None:
    assert normalize_whitespace("a\nb\r\nc\td") == "a b c d"


@pytest.mark.unit
def test_whitespace_preserves_single_space() -> None:
    assert normalize_whitespace("hello world") == "hello world"

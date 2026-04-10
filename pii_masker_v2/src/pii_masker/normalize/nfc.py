"""Unicode NFC normalization.

First step of the normalization pipeline. Canonicalizes decomposed combining
sequences so downstream regex matchers don't need to handle multiple encodings
of the same character.
"""
from __future__ import annotations

import unicodedata


def to_nfc(text: str) -> str:
    """Apply Unicode NFC normalization."""
    if not text:
        return text
    return unicodedata.normalize("NFC", text)

"""Regex for recognizing masking tokens in already-masked text.

A token is an uppercase bracketed identifier like `[NAME]`, `[CARD]`,
`[AMOUNT_TXN]`. The leak scanner uses this to distinguish "a detector fired
on an actual token" (fine) from "a detector fired on residual PII" (leak).
"""
from __future__ import annotations

import re
from typing import Pattern

TOKEN_RE: Pattern[str] = re.compile(r"\[[A-Z_]+\]")


def is_token(text: str) -> bool:
    """True if `text` is exactly one masking token."""
    return bool(TOKEN_RE.fullmatch(text))


def span_is_inside_token(text: str, start: int, end: int) -> bool:
    """True if `text[start:end]` is fully contained within a `[TOKEN]`.

    Used by the leak scanner to ignore detections whose spans are inside a
    legitimate masking token (e.g. a CVV detector matching the "3" in
    "[CVV]"... wait, no — CVVs are 3 digits and `[` is not a digit. But
    defensive: allow for future tokens like `[POLICY_123]`).
    """
    for m in TOKEN_RE.finditer(text):
        if m.start() <= start and end <= m.end():
            return True
    return False

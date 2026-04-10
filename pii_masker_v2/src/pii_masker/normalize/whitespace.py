"""Whitespace normalization.

Ports v3/v4 `_normalize_whitespace`. Collapses newlines/tabs to spaces and
runs of 2+ spaces to a single space, then trims.
"""
from __future__ import annotations

import re

_MULTI_SPACE_RE = re.compile(r"\s{2,}")


def normalize_whitespace(text: str) -> str:
    if not text:
        return text
    text = text.replace("\r\n", " ").replace("\n", " ").replace("\t", " ")
    return _MULTI_SPACE_RE.sub(" ", text).strip()

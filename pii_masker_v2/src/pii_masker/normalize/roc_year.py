"""ROC (Taiwanese) year → CE year conversion.

Ports v3/v4 `_roc_to_ce_year`. MUST run after `zh_numeral.to_arabic` so that
"民國一一三年" has already been rewritten to "民國113年" by the time we try
to parse the year.

The valid ROC year range is 10..150, which covers customers born from ROC 10
(CE 1921) through ROC 150 (CE 2061), matching v3/v4 Issue 6 fix.
"""
from __future__ import annotations

import re

_ROC_YEAR_RE = re.compile(r"(?:民(?:\u570b|\u56fd)?\s*)(\d{2,3})\s*\u5e74")
_ROC_BASE: int = 1911
_ROC_MIN: int = 10
_ROC_MAX: int = 150


def to_ce_year(text: str) -> str:
    """Convert "民國NNN年" → "(NNN+1911)年" when NNN is in the valid ROC range."""
    if not text:
        return text

    def _replace(m: re.Match[str]) -> str:
        roc = int(m.group(1))
        if _ROC_MIN <= roc <= _ROC_MAX:
            return f"{roc + _ROC_BASE}\u5e74"
        return m.group()

    return _ROC_YEAR_RE.sub(_replace, text)

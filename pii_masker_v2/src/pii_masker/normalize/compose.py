"""Step 0 — compose all normalization steps in a FIXED order.

ORDER IS LOAD-BEARING. Do not reorder without reading the two regression
tests in tests/unit/normalize/test_compose.py that pin this invariant.

The order mirrors v3/v4 `normalizer.normalize`:

1. NFC (canonicalize decomposed combining sequences)
2. Full-width → half-width
3. Chinese numeral → Arabic (必須在民國年之前!)
4. ROC year → CE year (depends on (3) having run)
5. STT filler repeat collapse
6. Whitespace normalization
"""
from __future__ import annotations

from pii_masker.normalize.fullwidth import to_halfwidth
from pii_masker.normalize.nfc import to_nfc
from pii_masker.normalize.roc_year import to_ce_year
from pii_masker.normalize.stt_filler import clean_filler_repeats
from pii_masker.normalize.whitespace import normalize_whitespace
from pii_masker.normalize.zh_numeral import to_arabic


def normalize(text: str) -> str:
    """Apply all normalization steps in the fixed order."""
    if not text:
        return text
    text = to_nfc(text)
    text = to_halfwidth(text)
    text = to_arabic(text)      # MUST run before to_ce_year
    text = to_ce_year(text)
    text = clean_filler_repeats(text)
    text = normalize_whitespace(text)
    return text

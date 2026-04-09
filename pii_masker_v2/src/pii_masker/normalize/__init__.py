"""Step 0 — text normalization.

Each submodule is a pure function. `compose.normalize` chains them in a
fixed order. The order is LOAD-BEARING — Chinese numeral conversion MUST run
before ROC year conversion, otherwise "民國一一三年" cannot be parsed.

This ordering is the v3/v4 Issue 1 bug fix. Do not reorder without reading
the comment in `compose.py` and the corresponding regression test.
"""

from pii_masker.normalize.compose import normalize

__all__ = ["normalize"]

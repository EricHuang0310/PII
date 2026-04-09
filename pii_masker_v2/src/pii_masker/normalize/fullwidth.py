"""Full-width → half-width conversion.

Ports the `_FULLWIDTH_TABLE` from v3/v4 `normalizer.py` verbatim. The table is
frozen at module import time so every call uses the same str.translate table.
"""
from __future__ import annotations

# Full-width source characters (same as v3/v4 _FW_SRC, byte-for-byte).
_FW_SRC: str = (
    "\u3000\uff01\uff02\uff03\uff04\uff05\uff06\uff07\uff08\uff09\uff0a\uff0b"
    "\uff0c\uff0d\uff0e\uff0f"
    "\uff10\uff11\uff12\uff13\uff14\uff15\uff16\uff17\uff18\uff19"
    "\uff1a\uff1b\uff1c\uff1d\uff1e\uff1f\uff20"
    "\uff21\uff22\uff23\uff24\uff25\uff26\uff27\uff28\uff29\uff2a"
    "\uff2b\uff2c\uff2d\uff2e\uff2f\uff30\uff31\uff32\uff33\uff34"
    "\uff35\uff36\uff37\uff38\uff39\uff3a"
    "\uff3b\uff3c\uff3d\uff3e\uff3f\uff40"
    "\uff41\uff42\uff43\uff44\uff45\uff46\uff47\uff48\uff49\uff4a"
    "\uff4b\uff4c\uff4d\uff4e\uff4f\uff50\uff51\uff52\uff53\uff54"
    "\uff55\uff56\uff57\uff58\uff59\uff5a"
    "\uff5b\uff5c\uff5d\uff5e"
)
_FW_DST: str = (
    " !\"#$%&'()*+"
    ",-./0123456789"
    ":;<=>?@"
    "ABCDEFGHIJ"
    "KLMNOPQRST"
    "UVWXYZ"
    "[\\]^_`"
    "abcdefghij"
    "klmnopqrst"
    "uvwxyz"
    "{|}~"
)

assert len(_FW_SRC) == len(_FW_DST), (
    f"fullwidth table mismatch: {len(_FW_SRC)} src vs {len(_FW_DST)} dst"
)

_FULLWIDTH_TABLE = str.maketrans(_FW_SRC, _FW_DST)
_IDEOGRAPHIC_SPACE = "\u3000"


def to_halfwidth(text: str) -> str:
    """Convert full-width ASCII / ideographic space to half-width."""
    if not text:
        return text
    text = text.replace(_IDEOGRAPHIC_SPACE, " ")
    return text.translate(_FULLWIDTH_TABLE)

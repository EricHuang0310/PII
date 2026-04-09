"""Post-filter validators — Luhn, TW ID checksum, etc.

These run after the base regex matches and can drop false positives. They are
opt-in via the `strict_validation` flag in MaskingPolicy so the default path
stays byte-compatible with v3/v4 (which does NOT validate checksums).
"""
from __future__ import annotations

from pii_masker.domain.detection import Detection

# TW national ID first letter → region code mapping (A..Z → 10..35)
_TW_ID_LETTER_VALUE: dict[str, int] = {
    "A": 10, "B": 11, "C": 12, "D": 13, "E": 14, "F": 15, "G": 16, "H": 17,
    "I": 34, "J": 18, "K": 19, "L": 20, "M": 21, "N": 22, "O": 35, "P": 23,
    "Q": 24, "R": 25, "S": 26, "T": 27, "U": 28, "V": 29, "W": 32, "X": 30,
    "Y": 31, "Z": 33,
}


def luhn_valid(digits: str) -> bool:
    """Standard Luhn check-digit validation. Used for credit card numbers."""
    if not digits or not digits.isdigit():
        return False
    total = 0
    parity = len(digits) % 2
    for i, ch in enumerate(digits):
        d = ord(ch) - ord("0")
        if i % 2 == parity:
            d *= 2
            if d > 9:
                d -= 9
        total += d
    return total % 10 == 0


def tw_id_valid(candidate: str) -> bool:
    """Validate the Taiwanese national ID check digit.

    Format: [A-Z][12]\\d{8}. First letter maps to two digits via
    _TW_ID_LETTER_VALUE, then the weighted sum modulo 10 must be 0.
    """
    s = candidate.upper()
    if len(s) != 10:
        return False
    letter, rest = s[0], s[1:]
    if letter not in _TW_ID_LETTER_VALUE or not rest.isdigit():
        return False
    n1, n2 = divmod(_TW_ID_LETTER_VALUE[letter], 10)
    digits = [n1, n2] + [int(c) for c in rest]
    # weights: 1, 9, 8, 7, 6, 5, 4, 3, 2, 1, 1
    weights = [1, 9, 8, 7, 6, 5, 4, 3, 2, 1, 1]
    total = sum(d * w for d, w in zip(digits, weights))
    return total % 10 == 0


def make_luhn_filter() -> "callable[[Detection, str], bool]":  # type: ignore[name-defined]
    """Post-filter factory: keep Detection only if its digits pass Luhn."""

    def _filter(det: Detection, _text: str) -> bool:
        return luhn_valid(det.raw_text)

    return _filter


def make_tw_id_filter() -> "callable[[Detection, str], bool]":  # type: ignore[name-defined]
    """Post-filter factory: keep Detection only if its TW ID checksum matches."""

    def _filter(det: Detection, _text: str) -> bool:
        return tw_id_valid(det.raw_text)

    return _filter

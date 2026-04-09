"""Chinese numeral → Arabic numeral conversion.

Ports v3/v4 `_parse_zh_number` and `_zh_digits_to_arabic` verbatim. Three cases:

1. Positional numerals with 十/百/千 (e.g., 七十四 → 74)
2. Single digit + time unit (e.g., 三月 → 3月)
3. Consecutive plain digits (e.g., 一一三 → 113)

All three must run in this order and this entire module must run BEFORE the
ROC year converter — otherwise "民國一一三年" cannot be parsed.
"""
from __future__ import annotations

import re

_ZH_UNIT: dict[str, int] = {
    "\u96f6": 0, "\u3007": 0,   # 零〇
    "\u4e00": 1, "\u58f9": 1,   # 一壹
    "\u4e8c": 2, "\u8cb3": 2,   # 二貳
    "\u4e09": 3, "\u53c3": 3,   # 三參
    "\u56db": 4, "\u8086": 4,   # 四肆
    "\u4e94": 5, "\u4f0d": 5,   # 五伍
    "\u516d": 6, "\u9678": 6,   # 六陸
    "\u4e03": 7, "\u67d2": 7,   # 七柒
    "\u516b": 8, "\u634c": 8,   # 八捌
    "\u4e5d": 9, "\u7396": 9,   # 九玖
}

_ZH_POS: dict[str, int] = {
    "\u5341": 10,    # 十
    "\u767e": 100,   # 百
    "\u5343": 1000,  # 千
}

_ALL_ZH_DIGITS: frozenset[str] = frozenset(_ZH_UNIT.keys()) | frozenset(_ZH_POS.keys())

_ZH_WITH_POS_RE = re.compile(
    "[" + "".join(re.escape(c) for c in _ALL_ZH_DIGITS) + "]*"
    "[\u5341\u767e\u5343]"   # must contain 十/百/千
    "[" + "".join(re.escape(c) for c in _ALL_ZH_DIGITS) + "]*"
)

_SINGLE_UNIT_RE = re.compile(
    "([" + "".join(re.escape(c) for c in _ZH_UNIT.keys()) + "])"
    "([\u6708\u65e5\u865f\u9ede])"   # 月 日 號 點
)

_ZH_CONSECUTIVE_RE = re.compile(
    "[" + "".join(re.escape(c) for c in _ZH_UNIT.keys()) + "]{2,}"
)


def _parse_zh_number(s: str) -> str:
    """Parse a positional Chinese numeral into an Arabic digit string.

    Returns the original string if parsing yields 0 (i.e., no digits were
    found), to match v3/v4 behavior.
    """
    total = 0
    current = 0
    chars = list(s)
    i = 0
    while i < len(chars):
        c = chars[i]
        if c in _ZH_UNIT:
            current = _ZH_UNIT[c]
            i += 1
        elif c in _ZH_POS:
            pos = _ZH_POS[c]
            if c == "\u5341" and current == 0 and i == 0:
                current = 1  # 十X at start = 1×10
            total += current * pos
            current = 0
            i += 1
        else:
            break
    total += current
    return str(total) if total > 0 else s


def to_arabic(text: str) -> str:
    """Three-step Chinese numeral → Arabic conversion.

    Step A: positional numerals (七十四 → 74)
    Step B: single digit + time unit (三月 → 3月)
    Step C: consecutive plain digits (一一三 → 113)
    """
    if not text:
        return text

    # Step A
    text = _ZH_WITH_POS_RE.sub(lambda m: _parse_zh_number(m.group()), text)
    # Step B
    text = _SINGLE_UNIT_RE.sub(
        lambda m: str(_ZH_UNIT.get(m.group(1), m.group(1))) + m.group(2),
        text,
    )
    # Step C
    text = _ZH_CONSECUTIVE_RE.sub(
        lambda m: "".join(str(_ZH_UNIT.get(c, c)) for c in m.group()),
        text,
    )
    return text

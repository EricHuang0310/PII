"""STT filler-word repeat collapsing.

Ports v3/v4 `_clean_stt_repeats`. CRITICAL: only collapses repeats of explicit
filler characters (啊喔嗯欸...). Never collapses generic CJK. Generic
collapsing would break PII detection — e.g., "三三三五" is a legitimate account
suffix that `_ZH_CONSECUTIVE_RE` converts to "3335".
"""
from __future__ import annotations

import re

# The exact filler character set from v3/v4 normalizer.
_STT_FILLER_CHARS: str = "啊喔嗯欸哦呢吧吼哈呀哎唉那"

_REPEAT_FILLER_RE = re.compile(
    "([" + re.escape(_STT_FILLER_CHARS) + "])" + r"\1{2,}"
)


def clean_filler_repeats(text: str) -> str:
    """Collapse 3+ repeats of any filler character down to 2.

    Example: "嗯嗯嗯嗯" → "嗯嗯". Non-filler repeats are untouched.
    """
    if not text:
        return text
    return _REPEAT_FILLER_RE.sub(lambda m: m.group(1) * 2, text)

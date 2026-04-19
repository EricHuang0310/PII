"""
Duck-compatible dataclass，供 ConflictResolver 以 .entity_type / .start / .end /
.score / .analysis_explanation 存取。不依賴 Presidio 型別。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class Explanation:
    recognizer: str = ""
    pattern_name: Optional[str] = None
    score_context_improvement: float = 0.0
    supportive_context_word: Optional[str] = None


@dataclass
class Span:
    entity_type: str
    start: int
    end: int
    score: float
    analysis_explanation: Optional[Explanation] = None

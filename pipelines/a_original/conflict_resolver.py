# masking/conflict_resolver.py  v3
"""
★ v3 新增：Conflict Resolver
實作 Priority Engine（數字類排他規則）與 Conflict Resolution Matrix（多模型衝突解決）。

解決的問題：
  1. 數字類規則互相衝突（OTP/PIN/CVV/金額/帳號/卡號 完全重疊的數字空間）
  2. Regex / NER / LLM 命中重疊區段時的決策

解決策略（依序）：
  1. Longest Match Wins        — 長度較長的 span 優先
  2. Risk Level Priority       — 同長度時，風險等級較高者優先
  3. Entity Priority Score     — 同風險等級時，依 ENTITY_PRIORITY 順序決定
  4. Keyword Bonus             — 有關鍵字觸發的結果額外加分
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from presidio_analyzer import RecognizerResult

from .config import ENTITY_PRIORITY, ENTITY_RISK_LEVEL


# ══════════════════════════════════════════════════════════════
# 衝突解決矩陣
# ══════════════════════════════════════════════════════════════

@dataclass
class ScoredResult:
    """帶有優先級分數的 RecognizerResult 包裝器。"""
    result:         RecognizerResult
    priority_score: float = 0.0
    has_keyword:    bool  = False
    conflict_resolved: bool = False   # 是否曾參與衝突解決並勝出

    @property
    def span_length(self) -> int:
        return self.result.end - self.result.start

    @property
    def entity_type(self) -> str:
        return self.result.entity_type

    @property
    def start(self) -> int:
        return self.result.start

    @property
    def end(self) -> int:
        return self.result.end

    @property
    def risk_level(self) -> int:
        return ENTITY_RISK_LEVEL.get(self.entity_type, 0)

    @property
    def entity_priority(self) -> int:
        return ENTITY_PRIORITY.get(self.entity_type, 0)


def _compute_priority_score(
    result: RecognizerResult,
    has_keyword: bool,
) -> float:
    """
    計算最終優先級分數。
    公式：priority×0.4 + risk_level×10×0.4 + presidio_score×10×0.1 + keyword_bonus×0.1
    """
    priority   = ENTITY_PRIORITY.get(result.entity_type, 0)
    risk       = ENTITY_RISK_LEVEL.get(result.entity_type, 0) * 10
    p_score    = result.score * 10
    kw_bonus   = 10.0 if has_keyword else 0.0

    return priority * 0.4 + risk * 0.4 + p_score * 0.1 + kw_bonus * 0.1


def _has_keyword_context(
    result: RecognizerResult,
    text: str,
    window: int = 20,
) -> bool:
    """在匹配位置前後 window 字元內，是否出現關鍵字（從 analysis_explanation 取得）。"""
    if result.analysis_explanation and result.analysis_explanation.pattern_name:
        # Presidio 已做過 context 提升，視為有關鍵字
        return result.score > 0.7
    # 退而根據分數判斷（關鍵字命中後 Presidio 會提升分數）
    return result.score >= 0.70


class ConflictResolver:
    """
    衝突解決器。

    使用方式：
        resolver = ConflictResolver()
        clean_results = resolver.resolve(raw_results, text)
    """

    def resolve(
        self,
        results: List[RecognizerResult],
        text: str,
    ) -> Tuple[List[RecognizerResult], List[Tuple[str, str, str]]]:
        """
        對 Presidio 分析結果進行衝突解決。

        Args:
            results:  原始 RecognizerResult 列表（可能含重疊）
            text:     原始文字（用於 context 判斷）

        Returns:
            (clean_results, conflict_log)
            - clean_results:  去除衝突後的最終結果
            - conflict_log:   [(winner_type, loser_type, reason)] 供 Audit 使用
        """
        if not results:
            return [], []

        # Step A：計算每個 result 的優先級分數
        scored = [
            ScoredResult(
                result=r,
                priority_score=_compute_priority_score(
                    r, _has_keyword_context(r, text)
                ),
                has_keyword=_has_keyword_context(r, text),
            )
            for r in results
        ]

        # Step B：依 start 位置排序，相同 start 時長 span 優先
        scored.sort(key=lambda s: (s.start, -s.span_length, -s.priority_score))

        # Step C：依衝突類型處理
        kept:         List[ScoredResult] = []
        conflict_log: List[Tuple[str, str, str]] = []

        for current in scored:
            overlapping = [k for k in kept if self._overlaps(current, k)]

            if not overlapping:
                kept.append(current)
                continue

            # 找出衝突中最強的對手
            strongest = max(overlapping, key=lambda s: s.priority_score)

            winner, loser, reason = self._resolve_pair(current, strongest)

            if winner is current:
                # current 勝出：替換 strongest，保留其他未衝突的
                kept = [k for k in kept if k is not strongest]
                current.conflict_resolved = True
                kept.append(current)
                conflict_log.append((
                    current.entity_type,
                    strongest.entity_type,
                    reason,
                ))
            else:
                # current 落敗：直接丟棄
                conflict_log.append((
                    strongest.entity_type,
                    current.entity_type,
                    reason,
                ))

        # Step D：標記有參與衝突解決的結果
        for s in kept:
            if s.conflict_resolved:
                s.result.score = min(1.0, s.result.score + 0.05)

        return [s.result for s in kept], conflict_log

    # ── 衝突判斷 ─────────────────────────────────────────────

    @staticmethod
    def _overlaps(a: ScoredResult, b: ScoredResult) -> bool:
        """判斷兩個 span 是否重疊（不含緊鄰）。"""
        return a.start < b.end and a.end > b.start

    @staticmethod
    def _contains(outer: ScoredResult, inner: ScoredResult) -> bool:
        """outer 是否嚴格包含 inner（outer 必須比 inner 長，等長 span 不視為包含）。"""
        if outer.span_length <= inner.span_length:
            return False   # 等長或更短：不視為包含，走風險等級決勝
        return outer.start <= inner.start and outer.end >= inner.end

    def _resolve_pair(
        self,
        a: ScoredResult,
        b: ScoredResult,
    ) -> Tuple[ScoredResult, ScoredResult, str]:
        """
        解決兩個衝突 span 的勝負。

        衝突解決矩陣：
          1. 完全包含 → 保留較長者
          2. 部分重疊 → 風險等級高者優先；同級則長者優先；再同則 Priority Score
        """
        # Case 1：完全包含
        if self._contains(a, b):
            return (a, b, "CONTAINS:longer_wins")
        if self._contains(b, a):
            return (b, a, "CONTAINS:longer_wins")

        # Case 2：部分重疊
        # 2a. 風險等級決勝
        if a.risk_level != b.risk_level:
            winner, loser = (a, b) if a.risk_level > b.risk_level else (b, a)
            return (winner, loser, f"RISK_LEVEL:{winner.risk_level}>{loser.risk_level}")

        # 2b. Span 長度決勝
        if a.span_length != b.span_length:
            winner, loser = (a, b) if a.span_length > b.span_length else (b, a)
            return (winner, loser, f"SPAN_LENGTH:{winner.span_length}>{loser.span_length}")

        # 2c. Priority Score 決勝
        winner, loser = (a, b) if a.priority_score >= b.priority_score else (b, a)
        return (winner, loser, f"PRIORITY_SCORE:{winner.priority_score:.1f}>={loser.priority_score:.1f}")

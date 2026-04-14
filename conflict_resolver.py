# masking/conflict_resolver.py  v3
"""
★ v3 新增：Conflict Resolver
實作 Priority Engine（數字類排他規則）與 Conflict Resolution Matrix（多模型衝突解決）。

解決的問題：
  1. 數字類規則互相衝突（OTP/PIN/CVV/金額/帳號/卡號 完全重疊的數字空間）
  2. Regex / NER / LLM 命中重疊區段時的決策
  3. CKIP × Presidio 內建 spaCy NER × AddressEnhancedRecognizer 在相同 span
     上重複偵測 PERSON / LOCATION（相同 start/end/entity_type 的純重複）

解決策略（依序）：
  0. Exact Duplicate Dedup     — (start, end, entity_type) 完全相同時只保留 score 最高者
                                 （同分保留先出現者），其餘直接丟棄並記 conflict_log
  1. Longest Match Wins        — 長度較長的 span 優先
  2. Risk Level Priority       — 同長度時，風險等級較高者優先
  3. Entity Priority Score     — 同風險等級時，依 ENTITY_PRIORITY 順序決定
  4. Keyword Bonus             — 有關鍵字觸發的結果額外加分
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from presidio_analyzer import RecognizerResult

from config import ENTITY_PRIORITY, ENTITY_RISK_LEVEL


# Presidio 關鍵字觸發後的分數門檻（用於 _has_keyword_context 判斷）
_KEYWORD_SCORE_THRESHOLD: float = 0.70


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
    計算最終優先級分數（issue #4 修正）。

    舊公式 `priority×0.4 + risk×10×0.4 + score×10×0.1 + kw×0.1`：
      - priority (25-100) × 0.4 = 10-40   ← 主導
      - risk (1-5) × 10 × 0.4 = 4-20      ← 被壓扁
    然而 `_resolve_pair` Step 2a 先以 risk_level 決勝，當「選最強對手」時
    risk 反被 priority 蓋過（實例：OTP(risk=5) < PERSON(risk=4)）。

    新公式：risk 主導、priority 次之、score 第三、keyword 微調
      priority_score = risk × 20 + priority × 0.1 + score × 5 + (kw ? 2 : 0)

      - risk (1-5) × 20 = 20-100 （一個 risk step = 20 分）
      - priority (25-100) × 0.1 = 2.5-10 （< 一個 risk step，只能在同 risk 內決勝）
      - score (0-1) × 5 = 0-5
      - keyword bonus = 2 或 0 （最小微調）

    保證：高 risk 無 keyword > 低 risk + keyword（20 > 2）。
    """
    priority = ENTITY_PRIORITY.get(result.entity_type, 0)
    risk     = ENTITY_RISK_LEVEL.get(result.entity_type, 0)
    kw_bonus = 2.0 if has_keyword else 0.0

    return risk * 20.0 + priority * 0.1 + result.score * 5.0 + kw_bonus


def _has_keyword_context(result: RecognizerResult) -> bool:
    """
    判斷 result 是否有 context keyword 支撐。

    issue #3 修正：舊版兩個分支都只是 `score >= threshold`，text/window
    參數未使用，名實不符。新版改以 Presidio 的真實 context 訊號為準：

      1. `score_context_improvement > 0` — Presidio 因 context word 實際加過分
      2. `supportive_context_word` 非空 — Presidio 指出了觸發加分的關鍵字
      3. 以上皆無但 `score >= _KEYWORD_SCORE_THRESHOLD` — fallback 相容

    若 `analysis_explanation` 完全缺失，回傳 False（無證據不推斷）。
    """
    exp = result.analysis_explanation
    if exp is None:
        return False

    improvement = getattr(exp, "score_context_improvement", 0.0) or 0.0
    if improvement > 0.0:
        return True

    if getattr(exp, "supportive_context_word", None):
        return True

    return result.score >= _KEYWORD_SCORE_THRESHOLD


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
    ) -> Tuple[
        List[RecognizerResult],
        List[Tuple[RecognizerResult, RecognizerResult, str]],
    ]:
        """
        對 Presidio 分析結果進行衝突解決。

        Args:
            results:  原始 RecognizerResult 列表（可能含重疊）
            text:     原始文字（用於 context 判斷）

        Returns:
            (clean_results, conflict_log)
            - clean_results:  去除衝突後的最終結果
            - conflict_log:   [(winner_result, loser_result, reason)] — 存放
                              實際的 RecognizerResult 物件（非 entity_type 字串），
                              pipeline 端以 id(winner) 追蹤「勝出」記錄到 audit。
        """
        if not results:
            return [], []

        conflict_log: List[Tuple[RecognizerResult, RecognizerResult, str]] = []

        # Step 0：Exact Duplicate Dedup
        # 處理 CKIP × spaCy NER × AddressEnhancedRecognizer 對相同 span + 相同
        # entity_type 的純重複偵測。每組只保留 score 最高者，同分保留先出現者。
        deduped: List[RecognizerResult] = []
        winner_by_key: Dict[Tuple[int, int, str], RecognizerResult] = {}
        for r in results:
            key = (r.start, r.end, r.entity_type)
            existing = winner_by_key.get(key)
            if existing is None:
                winner_by_key[key] = r
                deduped.append(r)
                continue
            # 分數高者勝，同分保留先出現者（即 existing）
            if r.score > existing.score:
                # 新的 r 取代既有勝者：將 existing 降為落敗
                conflict_log.append((r, existing, "EXACT_DUP:higher_score_wins"))
                winner_by_key[key] = r
                # 在 deduped 中用 r 取代 existing（維持原本位置）
                deduped[deduped.index(existing)] = r
            else:
                # 既有勝者保留；r 落敗
                reason = (
                    "EXACT_DUP:higher_score_wins"
                    if existing.score > r.score
                    else "EXACT_DUP:first_wins"
                )
                conflict_log.append((existing, r, reason))

        # Step A：計算每個 result 的優先級分數
        # issue #3 修正：_has_keyword_context 不再需要 text / window，
        # 直接從 result.analysis_explanation 讀 Presidio 的 context 訊號
        scored = []
        for r in deduped:
            has_kw = _has_keyword_context(r)
            scored.append(ScoredResult(
                result=r,
                priority_score=_compute_priority_score(r, has_kw),
                has_keyword=has_kw,
            ))

        # Step B：依 start 位置排序，相同 start 時長 span 優先
        scored.sort(key=lambda s: (s.start, -s.span_length, -s.priority_score))

        # Step C：依衝突類型處理
        # issue #7：每次衝突附上 round index，conflict_log 可重建決策順序
        kept: List[ScoredResult] = []
        round_n = 0

        for current in scored:
            overlapping = [k for k in kept if self._overlaps(current, k)]

            if not overlapping:
                kept.append(current)
                continue

            round_n += 1
            # 找出衝突中最強的對手
            strongest = max(overlapping, key=lambda s: s.priority_score)

            winner, loser, reason = self._resolve_pair(current, strongest)
            # issue #5：exact (start,end) 相同但 type 不同 → 明確標記
            if (current.start == strongest.start and
                current.end == strongest.end and
                current.entity_type != strongest.entity_type):
                reason = f"CROSS_TYPE_SAME_SPAN:{reason}"
            reason = f"[R{round_n}] {reason}"

            if winner is current:
                # current 勝出：替換 strongest，保留其他未衝突的
                kept = [k for k in kept if k is not strongest]
                current.conflict_resolved = True
                kept.append(current)
                conflict_log.append((current.result, strongest.result, reason))
            else:
                # current 落敗：直接丟棄
                conflict_log.append((strongest.result, current.result, reason))

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

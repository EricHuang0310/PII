"""
ConflictResolver regression tests.

目標：
  1. 驗證 Step 0 Exact Dup dedup 行為
  2. 驗證 Step C 的連鎖衝突處理（原 issue #1：current 跟多個 kept 同時重疊）
  3. 驗證 kept 不變式：任何時刻 kept 中的 items 彼此不重疊

執行：pytest test_conflict_resolver.py -v
"""
from __future__ import annotations

import pytest
from presidio_analyzer import RecognizerResult

from conflict_resolver import ConflictResolver


def mk(entity_type: str, start: int, end: int, score: float = 0.8) -> RecognizerResult:
    return RecognizerResult(entity_type=entity_type, start=start, end=end, score=score)


def _overlaps(a: RecognizerResult, b: RecognizerResult) -> bool:
    return a.start < b.end and a.end > b.start


# ══════════════════════════════════════════════════════════════
# Step 0: Exact Duplicate Dedup
# ══════════════════════════════════════════════════════════════

def test_exact_dup_keeps_higher_score():
    r = ConflictResolver()
    a = mk("PERSON", 0, 3, score=0.70)
    b = mk("PERSON", 0, 3, score=0.90)
    kept, log = r.resolve([a, b], "王小明說")
    assert len(kept) == 1
    assert kept[0] is b
    assert any("EXACT_DUP" in entry[2] for entry in log)


def test_exact_dup_first_wins_on_tie():
    r = ConflictResolver()
    a = mk("PERSON", 0, 3, score=0.80)
    b = mk("PERSON", 0, 3, score=0.80)
    kept, log = r.resolve([a, b], "王小明說")
    assert len(kept) == 1
    assert kept[0] is a
    assert any("EXACT_DUP:first_wins" in entry[2] for entry in log)


def test_exact_dup_different_type_not_merged():
    """不同 entity_type 不走 Step 0 dedup，走 Step C。"""
    r = ConflictResolver()
    a = mk("PERSON", 0, 3, score=0.80)
    b = mk("LOCATION", 0, 3, score=0.80)
    kept, log = r.resolve([a, b], "王小明說")
    # 同 span 不同 type → Step C 會以 risk_level / priority 決勝，只剩一個
    assert len(kept) == 1


# ══════════════════════════════════════════════════════════════
# Step C: Contains
# ══════════════════════════════════════════════════════════════

def test_contains_longer_wins():
    r = ConflictResolver()
    short = mk("LOCATION", 4, 7)          # 台北市
    long_ = mk("LOCATION", 4, 16)         # 台北市忠孝東路100號
    kept, _ = r.resolve([short, long_], "我住在台北市忠孝東路100號")
    assert len(kept) == 1
    assert kept[0] is long_


# ══════════════════════════════════════════════════════════════
# 核心不變式：kept 裡的 items 彼此不重疊
# ══════════════════════════════════════════════════════════════

def test_kept_items_never_overlap_after_resolve():
    """
    壓力測試：丟入 30 個隨機重疊的 span，確保輸出沒有任何兩個互相重疊。
    """
    import random
    random.seed(42)
    raw = []
    types = ["PERSON", "LOCATION", "TW_PHONE", "AMOUNT", "TW_CREDIT_CARD"]
    for _ in range(30):
        s = random.randint(0, 50)
        length = random.randint(3, 15)
        raw.append(mk(random.choice(types), s, s + length, score=random.uniform(0.5, 0.95)))

    r = ConflictResolver()
    kept, _ = r.resolve(raw, "x" * 100)

    for i, a in enumerate(kept):
        for b in kept[i + 1 :]:
            assert not _overlaps(a, b), (
                f"kept 違反不變式：{a.entity_type}[{a.start}:{a.end}] "
                f"重疊 {b.entity_type}[{b.start}:{b.end}]"
            )


# ══════════════════════════════════════════════════════════════
# Issue #1：連鎖衝突 — current 跟多個 kept 同時重疊
# ══════════════════════════════════════════════════════════════

def test_chain_conflict_current_overlaps_multiple_kept():
    """
    假想情境：A=[0,5], B=[8,13], current=[3,12] 同時重疊 A 跟 B。
    """
    r = ConflictResolver()
    a = mk("PERSON", 0, 5, score=0.80)
    b = mk("TW_PHONE", 8, 13, score=0.80)
    current = mk("LOCATION", 3, 12, score=0.95)
    kept, _ = r.resolve([a, b, current], "x" * 20)

    for i, x in enumerate(kept):
        for y in kept[i + 1 :]:
            assert not _overlaps(x, y), (
                f"連鎖衝突 bug：kept 中 {x.entity_type}[{x.start}:{x.end}] "
                f"仍重疊 {y.entity_type}[{y.start}:{y.end}]"
            )


def test_chain_conflict_same_start_multiple_kept():
    """
    同起點但不同長度的三個 span — 測試 sort stability + contains 鏈式處理。
    """
    r = ConflictResolver()
    short = mk("PERSON", 0, 4, score=0.80)
    mid = mk("LOCATION", 0, 8, score=0.80)
    long_ = mk("TW_CREDIT_CARD", 0, 12, score=0.80)
    kept, _ = r.resolve([short, mid, long_], "x" * 20)

    assert len(kept) == 1  # CONTAINS:longer_wins 連鎖應只留最長
    assert kept[0] is long_


if __name__ == "__main__":
    import sys
    sys.exit(pytest.main([__file__, "-v"]))

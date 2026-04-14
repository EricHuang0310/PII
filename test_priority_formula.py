"""
_compute_priority_score regression tests — issue #4.

舊公式 `priority*0.4 + risk*10*0.4 + score*10*0.1 + kw*0.1`：
  - priority (25-100) * 0.4 = 10-40  ← 主導
  - risk (1-5) * 10 * 0.4 = 4-20     ← 被壓扁

但 `_resolve_pair` 先以 risk_level 決勝，priority_score 只在 tiebreak。
這意味「選最強對手」階段 risk 應該主導，公式卻被 priority 蓋過。

新公式：risk 主導、priority 次之、score 第三、keyword 微調。

執行：pytest test_priority_formula.py -v
"""
from __future__ import annotations

import pytest
from presidio_analyzer import RecognizerResult

from conflict_resolver import _compute_priority_score


def mk(entity_type: str, score: float = 0.8) -> RecognizerResult:
    return RecognizerResult(entity_type=entity_type, start=0, end=3, score=score)


def test_high_risk_low_priority_beats_low_risk_high_priority():
    """
    issue #4 修正的核心 regression case：
      OTP    (priority=75, risk=5)  ← 較低 priority 但最高 risk
      PERSON (priority=95, risk=4)  ← 較高 priority 但稍低 risk

    舊公式：PERSON 勝（54.8 > 50.8），priority 主導
    新公式：OTP 勝，risk 主導（符合 _resolve_pair Step 2a 邏輯）
    """
    otp    = _compute_priority_score(mk("OTP",    score=0.8), has_keyword=False)
    person = _compute_priority_score(mk("PERSON", score=0.8), has_keyword=False)
    assert otp > person, (
        f"risk 應主導 priority：OTP(risk=5)={otp:.2f}, PERSON(risk=4)={person:.2f}"
    )


def test_same_risk_higher_priority_wins():
    """同風險等級時，priority 較高者 priority_score 較高。"""
    from config import ENTITY_RISK_LEVEL, ENTITY_PRIORITY
    by_risk: dict[int, list[str]] = {}
    for t, r in ENTITY_RISK_LEVEL.items():
        by_risk.setdefault(r, []).append(t)
    eligible = [types for types in by_risk.values() if len(types) >= 2]
    if not eligible:
        pytest.skip("config 裡找不到同 risk 的兩個 entity type")

    pair = sorted(eligible[0], key=lambda t: ENTITY_PRIORITY[t])
    low_pri_type, high_pri_type = pair[0], pair[-1]
    if ENTITY_PRIORITY[low_pri_type] == ENTITY_PRIORITY[high_pri_type]:
        pytest.skip("找到的同 risk pair priority 也相同")

    a = _compute_priority_score(mk(low_pri_type, score=0.8), has_keyword=False)
    b = _compute_priority_score(mk(high_pri_type, score=0.8), has_keyword=False)
    assert b > a


def test_keyword_bonus_is_smaller_than_risk_step():
    """
    keyword bonus 只是微調，不能讓低 risk + keyword 超越高 risk 無 keyword。
    使用 config 中實際的 risk 最低與最高 type。
    """
    from config import ENTITY_RISK_LEVEL
    min_risk = min(ENTITY_RISK_LEVEL.values())
    max_risk = max(ENTITY_RISK_LEVEL.values())
    if min_risk == max_risk:
        pytest.skip("config risk 等級單一，無法比較")

    low_type = next(t for t, r in ENTITY_RISK_LEVEL.items() if r == min_risk)
    high_type = next(t for t, r in ENTITY_RISK_LEVEL.items() if r == min_risk + 1)

    low_plus_kw = _compute_priority_score(mk(low_type, score=1.0), has_keyword=True)
    high_no_kw = _compute_priority_score(mk(high_type, score=0.5), has_keyword=False)
    assert high_no_kw > low_plus_kw, (
        f"一個 risk step 應主導 keyword+score："
        f"{low_type}(risk={min_risk})+kw+score1.0={low_plus_kw:.2f}, "
        f"{high_type}(risk={min_risk+1})+score0.5={high_no_kw:.2f}"
    )


def test_monotonic_in_risk():
    """固定其他條件，risk 越高 priority_score 越高。"""
    from config import ENTITY_RISK_LEVEL
    by_risk = {}
    for t, r in ENTITY_RISK_LEVEL.items():
        by_risk.setdefault(r, t)
    if len(by_risk) < 2:
        pytest.skip("config 沒有足夠的 risk 等級")
    min_risk = min(by_risk.keys())
    max_risk = max(by_risk.keys())
    low = _compute_priority_score(mk(by_risk[min_risk], score=0.8), has_keyword=False)
    high = _compute_priority_score(mk(by_risk[max_risk], score=0.8), has_keyword=False)
    assert high > low


if __name__ == "__main__":
    import sys
    sys.exit(pytest.main([__file__, "-v"]))

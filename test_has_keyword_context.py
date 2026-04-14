"""
_has_keyword_context regression tests — issue #3.

舊版兩個分支回同值，text / window 參數完全未使用 — 名實不符。
修正後以 Presidio 的 `score_context_improvement` / `supportive_context_word`
作為真實 context 訊號，無訊號時才 fallback 到 score threshold。

執行：pytest test_has_keyword_context.py -v
"""
from __future__ import annotations

import pytest
from presidio_analyzer import RecognizerResult, AnalysisExplanation

from conflict_resolver import _has_keyword_context


def mk(score: float, *,
       context_improvement: float = 0.0,
       supportive_word: str | None = None,
       with_explanation: bool = True) -> RecognizerResult:
    exp: AnalysisExplanation | None = None
    if with_explanation:
        exp = AnalysisExplanation(
            recognizer="test",
            original_score=score - context_improvement,
            pattern_name="TEST",
        )
        exp.score_context_improvement = context_improvement
        exp.supportive_context_word = supportive_word
    return RecognizerResult(entity_type="X", start=0, end=3, score=score, analysis_explanation=exp)


def test_context_improvement_positive_returns_true():
    r = mk(score=0.50, context_improvement=0.35)
    assert _has_keyword_context(r) is True


def test_supportive_context_word_returns_true():
    r = mk(score=0.50, supportive_word="驗證碼")
    assert _has_keyword_context(r) is True


def test_low_score_no_context_signal_returns_false():
    r = mk(score=0.50)
    assert _has_keyword_context(r) is False


def test_high_score_no_context_still_true_via_fallback():
    """score >= threshold 時 fallback 為 True（相容舊行為）。"""
    r = mk(score=0.80)
    assert _has_keyword_context(r) is True


def test_no_analysis_explanation_returns_false():
    r = mk(score=0.50, with_explanation=False)
    assert _has_keyword_context(r) is False


def test_high_score_no_explanation_returns_false():
    r = mk(score=0.90, with_explanation=False)
    assert _has_keyword_context(r) is False


def test_accepts_single_arg_only():
    """新簽名只接受 result，不再有 text/window。"""
    import inspect
    sig = inspect.signature(_has_keyword_context)
    assert list(sig.parameters.keys()) == ["result"]


if __name__ == "__main__":
    import sys
    sys.exit(pytest.main([__file__, "-v"]))

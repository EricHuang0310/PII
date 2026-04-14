"""
_apply_speaker_aware_masking regression tests — issue #2.

驗證：
  1. 不 mutate 輸入的 RecognizerResult.score
  2. 重複呼叫冪等（idempotent）
  3. 同一 result 被多個問句 window 覆蓋時只加一次 boost
  4. diarization_available=True 時不做任何修改

執行：pytest test_speaker_aware.py -v
"""
from __future__ import annotations

import re

import pytest
from presidio_analyzer import RecognizerResult

from pipeline import MaskingPipeline


def mk(entity_type: str, start: int, end: int, score: float = 0.5) -> RecognizerResult:
    return RecognizerResult(entity_type=entity_type, start=start, end=end, score=score)


def make_stub(q_patterns: list[str], a_patterns: list[str]) -> MaskingPipeline:
    """繞過 __init__（避免載入 CKIP）建立只供此方法測試的 stub。"""
    obj = MaskingPipeline.__new__(MaskingPipeline)
    obj._agent_q_pattern = re.compile("|".join(q_patterns)) if q_patterns else re.compile("(?!x)x")
    obj._answer_patterns = [re.compile(p) for p in a_patterns]
    return obj


def test_does_not_mutate_input_score():
    pipeline = make_stub(["大名"], [])
    text = "請問您的大名是什麼請回答"
    r = mk("PERSON", 8, 11, score=0.70)
    pipeline._apply_speaker_aware_masking(text, [r], speaker=None, diarization_available=False)
    assert r.score == 0.70, f"輸入物件被就地修改：{r.score}"


def test_idempotent_across_calls():
    pipeline = make_stub(["大名"], [])
    text = "請問您的大名是什麼請回答"
    r = mk("PERSON", 8, 11, score=0.70)
    out1 = pipeline._apply_speaker_aware_masking(text, [r], None, False)
    # 第二次必須以「原始未 boost 的 r」為輸入，而非 out1，才能真正測冪等
    out2 = pipeline._apply_speaker_aware_masking(text, [r], None, False)
    assert out1[0].score == out2[0].score == 0.85, (
        f"非冪等或分數錯誤：out1={out1[0].score}, out2={out2[0].score}"
    )
    # 兩次呼叫皆不得修改原物件
    assert r.score == 0.70


def test_multiple_question_windows_boost_once():
    """同一 result 落在 2 個問句 window 內，boost 仍只套用一次（取 max）。"""
    pipeline = make_stub(["請問", "大名"], [])
    text = "請問您的大名是王小明先生"
    r = mk("PERSON", 10, 13, score=0.50)
    out = pipeline._apply_speaker_aware_masking(text, [r], None, False)
    assert abs(out[0].score - 0.65) < 1e-9, f"重複加 boost：{out[0].score}"


def test_diarization_available_no_change():
    pipeline = make_stub(["大名"], [])
    r = mk("PERSON", 8, 11, score=0.70)
    out = pipeline._apply_speaker_aware_masking("請問您的大名", [r], None, diarization_available=True)
    assert out[0] is r
    assert r.score == 0.70


def test_no_match_returns_unchanged_object():
    pipeline = make_stub(["大名"], [])
    r = mk("PERSON", 0, 3, score=0.70)
    out = pipeline._apply_speaker_aware_masking("無關文字內容", [r], None, False)
    assert out[0] is r


if __name__ == "__main__":
    import sys
    sys.exit(pytest.main([__file__, "-v"]))

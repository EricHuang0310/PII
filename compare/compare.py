"""
遮罩效果比較 Driver。

A: Presidio + spaCy zh_core_web_sm + 20 custom regex（無 CKIP）
B: CKIP + 20 純 regex recognizer（無 presidio / spacy）

固定 regex 覆蓋等同 20 個，差異只來自 NER 來源（spaCy vs CKIP）。

用法：
  python -m comparison.compare
或：
  cd /Users/longxia/Documents/PII && python comparison/compare.py
"""
from __future__ import annotations

import pathlib
import sys
import time
from typing import Any, Dict, List

# 讓 `python comparison/compare.py` 直接跑得起來：把 project root 加到 sys.path
_ROOT = pathlib.Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


TEST_CASES: List[str] = [
    "我叫王小明，卡號是1234567890123456",
    "我電話0912345678",
    "住在台北市忠孝東路100號",
    "驗證碼是654321",
    "轉帳到帳號123456789012",
    "我家住在好市多隔壁的SEVEN樓上",
    "生日是民國七十四年五月一日",
    "我的身分證A123456789",
    "母親的姓名是陳美玲",
    "我的Email是foo@example.com",
]


def _loaded(prefix: str) -> int:
    return sum(1 for m in sys.modules if m.startswith(prefix))


def run_pipeline_a(cases: List[str]) -> Dict[str, Any]:
    before_p = _loaded("presidio") + _loaded("spacy")
    from compare.pipeline_a import PipelineA

    t0 = time.perf_counter()
    p = PipelineA(score_threshold=0.50)
    init_time = time.perf_counter() - t0

    records = []
    t0 = time.perf_counter()
    for text in cases:
        masked, clean, log = p.mask(text)
        records.append({
            "original":  text,
            "masked":    masked,
            "entities":  [(s.entity_type, text[s.start:s.end]) for s in clean],
            "conflicts": len(log),
        })
    mask_time = time.perf_counter() - t0

    return {
        "label":     "A (Presidio+spaCy+20 regex)",
        "init_time": init_time,
        "mask_time": mask_time,
        "records":   records,
        "modules":   _loaded("presidio") + _loaded("spacy") - before_p,
    }


def run_pipeline_b(cases: List[str]) -> Dict[str, Any]:
    before_p = _loaded("presidio") + _loaded("spacy")
    from pipelines.b_pure.pipeline import PipelineB

    t0 = time.perf_counter()
    p = PipelineB(with_ckip=True)
    init_time = time.perf_counter() - t0

    records = []
    t0 = time.perf_counter()
    for text in cases:
        masked, clean, log = p.mask(text)
        records.append({
            "original":  text,
            "masked":    masked,
            "entities":  [(s.entity_type, text[s.start:s.end]) for s in clean],
            "conflicts": len(log),
        })
    mask_time = time.perf_counter() - t0

    return {
        "label":     "B (CKIP+20 pure regex)",
        "init_time": init_time,
        "mask_time": mask_time,
        "records":   records,
        "modules":   _loaded("presidio") + _loaded("spacy") - before_p,
    }


def _ner_only_entities(entities: List[tuple]) -> set:
    """只比 NER 類型的差異：PERSON / LOCATION。"""
    return {(t, v) for t, v in entities if t in ("PERSON", "LOCATION")}


def print_report(a: Dict[str, Any], b: Dict[str, Any]) -> None:
    width = 82
    print()
    print("=" * width)
    print("  逐案遮罩比對")
    print("=" * width)

    match_count = 0
    ner_divergent = 0
    a_ner_only: List[tuple] = []
    b_ner_only: List[tuple] = []

    for fa, fb in zip(a["records"], b["records"]):
        same = fa["masked"] == fb["masked"]
        if same:
            match_count += 1
        flag = "一致" if same else "差異"
        print(f"\n[{flag}] 原文：{fa['original']}")
        print(f"   A: {fa['masked']}   [{len(fa['entities'])} ent, {fa['conflicts']} 衝突]")
        print(f"   B: {fb['masked']}   [{len(fb['entities'])} ent, {fb['conflicts']} 衝突]")

        a_ner = _ner_only_entities(fa["entities"])
        b_ner = _ner_only_entities(fb["entities"])
        a_only_ner = a_ner - b_ner
        b_only_ner = b_ner - a_ner
        if a_only_ner or b_only_ner:
            ner_divergent += 1
            if a_only_ner:
                print(f"     A(spaCy) 獨有 NER: {sorted(a_only_ner)}")
                a_ner_only.extend(a_only_ner)
            if b_only_ner:
                print(f"     B(CKIP)  獨有 NER: {sorted(b_only_ner)}")
                b_ner_only.extend(b_only_ner)

        if not same and not (a_only_ner or b_only_ner):
            a_set = {(t, v) for t, v in fa["entities"]}
            b_set = {(t, v) for t, v in fb["entities"]}
            a_only = a_set - b_set
            b_only = b_set - a_set
            if a_only:
                print(f"     A 獨有: {sorted(a_only)}")
            if b_only:
                print(f"     B 獨有: {sorted(b_only)}")

    n = len(a["records"])
    print()
    print("=" * width)
    print("  摘要")
    print("=" * width)
    print(f"  遮罩一致: {match_count}/{n}   NER 差異案例: {ner_divergent}/{n}")
    if a_ner_only:
        print(f"  A 獨抓的 NER (spaCy): {a_ner_only}")
    if b_ner_only:
        print(f"  B 獨抓的 NER (CKIP):  {b_ner_only}")
    print()
    print(f"  {'指標':<32}{'A':>22}{'B':>22}")
    print(f"  {'-'*76}")
    print(f"  {'初始化時間 (s)':<32}{a['init_time']:>22.2f}{b['init_time']:>22.2f}")
    print(f"  {'遮罩總時間 (s)':<32}{a['mask_time']:>22.2f}{b['mask_time']:>22.2f}")
    print(f"  {'平均每句 (ms)':<32}{a['mask_time']/n*1000:>22.1f}{b['mask_time']/n*1000:>22.1f}")
    print(f"  {'runtime 新增 presidio+spacy 模組':<32}{a['modules']:>22}{b['modules']:>22}")


def main():
    print("[A] 初始化 Presidio + spaCy + 20 regex（首次會下載 zh_core_web_sm）...", flush=True)
    try:
        a = run_pipeline_a(TEST_CASES)
    except Exception as e:
        print(f"[錯誤] A 初始化失敗：{e}")
        return
    print(f"  A 完成：init={a['init_time']:.2f}s, mask={a['mask_time']:.2f}s", flush=True)

    print("[B] 初始化 CKIP + 20 pure regex ...", flush=True)
    try:
        b = run_pipeline_b(TEST_CASES)
    except Exception as e:
        print(f"[錯誤] B 初始化失敗：{e}")
        return
    print(f"  B 完成：init={b['init_time']:.2f}s, mask={b['mask_time']:.2f}s", flush=True)

    print_report(a, b)


if __name__ == "__main__":
    main()

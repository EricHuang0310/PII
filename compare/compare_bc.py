"""
pipeline_b vs pipeline_c（合併版）遮罩效果比較。

B: CKIP + 20 pure regex
C: B + normalizer + PseudonymTracker(_1/_2) + bank rules
"""
from __future__ import annotations

import pathlib
import sys
import time
from typing import Any, Dict, List, Tuple
import warnings

warnings.filterwarnings("ignore")

_ROOT = pathlib.Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


TEST_CASES: List[Tuple[str, str]] = [
    ("全形/民國年", "生日是民國七十四年五月一日"),
    ("全形逗號",   "我叫王小明，卡號是1234567890123456"),
    ("STT 重複",   "嗯嗯嗯嗯我的卡號是1234567890123456"),
    ("中文數字",   "卡號末四碼是三三三五"),
    ("同人多次",   "我叫王小明，我就是王小明"),
    ("多人區分",   "王小明跟陳美玲一起來分行"),
    ("一般金額",   "今天氣溫30度，油價30元"),
    ("交易金額",   "幫我轉帳500元到帳號123456789012"),
    ("條件式 AMOUNT", "這張卡號1234567890123456扣了1000元"),
    ("電話 vs 帳號", "我電話0912345678"),
]


def run_b(cases: List[Tuple[str, str]]) -> Dict[str, Any]:
    from pipelines.b_pure.pipeline import PipelineB
    t0 = time.perf_counter()
    p = PipelineB(with_ckip=True)
    init_time = time.perf_counter() - t0

    rows = []
    t0 = time.perf_counter()
    for label, text in cases:
        masked, clean, log = p.mask(text)
        rows.append({
            "label":    label,
            "original": text,
            "masked":   masked,
            "entities": [(s.entity_type, text[s.start:s.end]) for s in clean],
        })
    return {"init_time": init_time,
            "mask_time": time.perf_counter() - t0,
            "rows": rows,
            "label": "B (CKIP + 20 pure regex)"}


def run_c(cases: List[Tuple[str, str]]) -> Dict[str, Any]:
    from pipelines.c_merged.pipeline import PipelineC
    from pipelines.a_original.pseudonym import PseudonymTracker
    t0 = time.perf_counter()
    p = PipelineC(with_ckip=True)
    init_time = time.perf_counter() - t0

    rows = []
    t0 = time.perf_counter()
    for label, text in cases:
        tracker = PseudonymTracker(session_id=label)
        normalized, masked, clean, log, pmap = p.mask(text, tracker=tracker)
        rows.append({
            "label":      label,
            "original":   text,
            "normalized": normalized,
            "masked":     masked,
            "entities":   [(s.entity_type, normalized[s.start:s.end]) for s in clean],
            "pmap":       pmap,
        })
    return {"init_time": init_time,
            "mask_time": time.perf_counter() - t0,
            "rows": rows,
            "label": "C = B + normalizer + PseudonymTracker + bank rules"}


def print_report(b: Dict[str, Any], c: Dict[str, Any]) -> None:
    w = 92
    print()
    print("=" * w)
    print(f"  {b['label']}")
    print(f"    vs")
    print(f"  {c['label']}")
    print("=" * w)

    match = 0
    for rb, rc in zip(b["rows"], c["rows"]):
        same = rb["masked"] == rc["masked"]
        if same:
            match += 1
        flag = "一致" if same else "差異"
        print(f"\n[{flag}][{rb['label']}] 原文: {rb['original']}")
        if rc.get("normalized") and rc["normalized"] != rb["original"]:
            print(f"   C 正規化: {rc['normalized']}")
        print(f"   B: {rb['masked']}")
        print(f"   C: {rc['masked']}")
        if rc.get("pmap"):
            non_empty = {k: v for k, v in rc["pmap"].items() if v}
            if non_empty:
                print(f"     C pseudonym_map: {non_empty}")

    n = len(b["rows"])
    print()
    print("=" * w)
    print("  摘要")
    print("=" * w)
    print(f"  遮罩一致: {match}/{n}   差異: {n - match}/{n}")
    print(f"  {'指標':<28}{'B':>26}{'C':>26}")
    print(f"  {'-'*80}")
    print(f"  {'初始化時間 (s)':<28}{b['init_time']:>26.2f}{c['init_time']:>26.2f}")
    print(f"  {'遮罩總時間 (s)':<28}{b['mask_time']:>26.2f}{c['mask_time']:>26.2f}")
    print(f"  {'平均每句 (ms)':<28}{b['mask_time']/n*1000:>26.1f}{c['mask_time']/n*1000:>26.1f}")


def main():
    print("[B] 初始化 ...", flush=True)
    try:
        b = run_b(TEST_CASES)
    except Exception as e:
        print(f"[錯誤] B：{type(e).__name__}: {e}")
        import traceback; traceback.print_exc(); return
    print(f"  B 完成：init={b['init_time']:.2f}s, mask={b['mask_time']:.2f}s")

    print("[C] 初始化（合併版）...", flush=True)
    try:
        c = run_c(TEST_CASES)
    except Exception as e:
        print(f"[錯誤] C：{type(e).__name__}: {e}")
        import traceback; traceback.print_exc(); return
    print(f"  C 完成：init={c['init_time']:.2f}s, mask={c['mask_time']:.2f}s")

    print_report(b, c)


if __name__ == "__main__":
    main()

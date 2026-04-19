"""
A（原版）/ B（pipeline_b）/ C（pipeline_c 合併版）三方遮罩效果比較。

A: original_file/pipeline.py (Presidio + spaCy + 17 regex + normalizer + pseudonym)
B: comparison/pipeline_b.py  (CKIP + 20 pure regex)
C: comparison/pipeline_c.py  (B 骨幹 + normalizer + PseudonymTracker + bank rules)
"""
from __future__ import annotations

import pathlib
import sys
import time
import warnings
from typing import List, Tuple

warnings.filterwarnings("ignore")

_ROOT = pathlib.Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


# Presidio 版本 shim（讓原版 pipeline 能在新版 Presidio 上跑起來）
def _install_presidio_shim() -> None:
    import regex as _regex
    from presidio_analyzer import RecognizerRegistry as _RR
    _orig = _RR.__init__
    default_flags = _regex.DOTALL | _regex.MULTILINE | _regex.IGNORECASE

    def _patched(self, recognizers=None, global_regex_flags=None,
                 supported_languages=None, *args, **kwargs):
        if supported_languages is None:
            supported_languages = ["zh", "en"]
        if global_regex_flags is None:
            global_regex_flags = default_flags
        _orig(self, recognizers=recognizers,
              global_regex_flags=global_regex_flags,
              supported_languages=supported_languages,
              *args, **kwargs)
    _RR.__init__ = _patched
_install_presidio_shim()


TEST_CASES: List[Tuple[str, str]] = [
    ("全形/民國年",    "生日是民國七十四年五月一日"),
    ("全形逗號",      "我叫王小明，卡號是1234567890123456"),
    ("STT 重複",       "嗯嗯嗯嗯我的卡號是1234567890123456"),
    ("中文數字",      "卡號末四碼是三三三五"),
    ("同人多次",      "我叫王小明，我就是王小明"),
    ("多人區分",      "王小明跟陳美玲一起來分行"),
    ("一般金額",      "今天氣溫30度，油價30元"),
    ("電話 vs 帳號",   "我電話0912345678"),
    ("驗證碼 OTP",     "驗證碼是654321"),
    ("Email 邊界",     "我的Email是foo@example.com"),
]


def run_a(cases):
    from pipelines.a_original.pipeline import MaskingPipeline
    t0 = time.perf_counter()
    p = MaskingPipeline(log_path=None, score_threshold=0.50)
    init_time = time.perf_counter() - t0
    rows = []
    t0 = time.perf_counter()
    for label, text in cases:
        r = p.mask(text=text, session_id="abc")
        rows.append({"label": label, "original": text,
                     "normalized": r.normalized_text, "masked": r.masked_text})
    return {"label": "A 原版 (Presidio+spaCy+17 regex+normalizer)",
            "init_time": init_time,
            "mask_time": time.perf_counter() - t0, "rows": rows}


def run_b(cases):
    from pipelines.b_pure.pipeline import PipelineB
    t0 = time.perf_counter()
    p = PipelineB(with_ckip=True)
    init_time = time.perf_counter() - t0
    rows = []
    t0 = time.perf_counter()
    for label, text in cases:
        masked, _, _ = p.mask(text)
        rows.append({"label": label, "original": text,
                     "normalized": text, "masked": masked})
    return {"label": "B (CKIP + 20 pure regex)",
            "init_time": init_time,
            "mask_time": time.perf_counter() - t0, "rows": rows}


def run_c(cases):
    from pipelines.c_merged.pipeline import PipelineC
    t0 = time.perf_counter()
    p = PipelineC(with_ckip=True)
    init_time = time.perf_counter() - t0
    rows = []
    t0 = time.perf_counter()
    for label, text in cases:
        normalized, masked, _, _, _ = p.mask(text)
        rows.append({"label": label, "original": text,
                     "normalized": normalized, "masked": masked})
    return {"label": "C = B + normalizer + PseudonymTracker + bank rules",
            "init_time": init_time,
            "mask_time": time.perf_counter() - t0, "rows": rows}


def print_report(a, b, c):
    w = 100
    print()
    print("=" * w)
    print(f"  A: {a['label']}")
    print(f"  B: {b['label']}")
    print(f"  C: {c['label']}")
    print("=" * w)

    for ra, rb, rc in zip(a["rows"], b["rows"], c["rows"]):
        print(f"\n[{ra['label']}] 原文: {ra['original']}")
        if ra["normalized"] != ra["original"]:
            print(f"   A 正規化: {ra['normalized']}")
        if rc["normalized"] != rc["original"]:
            print(f"   C 正規化: {rc['normalized']}")
        print(f"   A: {ra['masked']}")
        print(f"   B: {rb['masked']}")
        print(f"   C: {rc['masked']}")

    n = len(a["rows"])
    print()
    print("=" * w)
    print("  摘要")
    print("=" * w)
    print(f"  {'指標':<28}{'A':>24}{'B':>24}{'C':>24}")
    print(f"  {'-'*100}")
    print(f"  {'初始化時間 (s)':<28}{a['init_time']:>24.2f}{b['init_time']:>24.2f}{c['init_time']:>24.2f}")
    print(f"  {'遮罩總時間 (s)':<28}{a['mask_time']:>24.2f}{b['mask_time']:>24.2f}{c['mask_time']:>24.2f}")
    print(f"  {'平均每句 (ms)':<28}{a['mask_time']/n*1000:>24.1f}{b['mask_time']/n*1000:>24.1f}{c['mask_time']/n*1000:>24.1f}")


def main():
    print("[A] 初始化 Presidio + spaCy + 17 regex ...", flush=True)
    try:
        a = run_a(TEST_CASES)
    except Exception as e:
        print(f"[錯誤] A：{type(e).__name__}: {e}")
        import traceback; traceback.print_exc(); return
    print(f"  A 完成：init={a['init_time']:.2f}s, mask={a['mask_time']:.2f}s")

    print("[B] 初始化 CKIP + 20 pure regex ...", flush=True)
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

    print_report(a, b, c)


if __name__ == "__main__":
    main()

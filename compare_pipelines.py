"""
比較兩套 PII 遮罩管線在相同語料上的效果與性能。

A: FULL     — pipeline.MaskingPipeline      (Presidio + spaCy zh_core_web_sm + CKIP + 20+ regex)
B: MINIMAL  — minimal_pipeline.MinimalPipeline (CKIP + 5 regex，完全不載 Presidio/spaCy)

指標：
  1. 遮罩輸出是否一致
  2. 實體偵測差異（誰多抓、誰漏抓）
  3. 衝突紀錄數
  4. 初始化 + 逐句推論時間
  5. Runtime 載入的 presidio/spacy module 數

用法：python compare_pipelines.py
"""
from __future__ import annotations

import sys
import time
from typing import Any, Dict, List


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


def _loaded_modules(prefix: str) -> int:
    return sum(1 for m in sys.modules if m.startswith(prefix))


def run_full(cases: List[str]) -> Dict[str, Any]:
    from pipeline import MaskingPipeline
    before_full = _loaded_modules("presidio") + _loaded_modules("spacy")

    t0 = time.perf_counter()
    p = MaskingPipeline(log_path=None, score_threshold=0.50)
    init_time = time.perf_counter() - t0

    records = []
    t0 = time.perf_counter()
    for text in cases:
        r = p.mask(text=text, session_id="cmp", diarization_available=True)
        records.append({
            "original":  text,
            "masked":    r.masked_text,
            "entities":  [
                (e.entity_type, r.normalized_text[e.start:e.end])
                for e in r.entities_found
            ],
            "conflicts": len(r.conflict_log),
        })
    mask_time = time.perf_counter() - t0

    return {
        "label":       "FULL (Presidio+spaCy+CKIP+20regex)",
        "init_time":   init_time,
        "mask_time":   mask_time,
        "records":     records,
        "modules":     _loaded_modules("presidio") + _loaded_modules("spacy") - before_full,
    }


def run_minimal(cases: List[str]) -> Dict[str, Any]:
    from minimal_pipeline import MinimalPipeline
    before = _loaded_modules("presidio") + _loaded_modules("spacy")

    t0 = time.perf_counter()
    p = MinimalPipeline(with_ckip=True)
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
        "label":       "MINIMAL (CKIP+5regex)",
        "init_time":   init_time,
        "mask_time":   mask_time,
        "records":     records,
        "modules":     _loaded_modules("presidio") + _loaded_modules("spacy") - before,
    }


def print_comparison(full: Dict[str, Any], minimal: Dict[str, Any]) -> None:
    width = 80
    print()
    print("=" * width)
    print("  遮罩結果逐句比對")
    print("=" * width)

    match_count = 0
    for f, m in zip(full["records"], minimal["records"]):
        same = f["masked"] == m["masked"]
        if same:
            match_count += 1
        flag = "一致" if same else "差異"
        print(f"\n[{flag}] 原文：{f['original']}")
        print(f"   FULL   : {f['masked']}   [{len(f['entities'])} ent, {f['conflicts']} 衝突]")
        print(f"   MINIMAL: {m['masked']}   [{len(m['entities'])} ent, {m['conflicts']} 衝突]")
        if not same:
            f_set = {(t, v) for t, v in f["entities"]}
            m_set = {(t, v) for t, v in m["entities"]}
            only_full = f_set - m_set
            only_min  = m_set - f_set
            if only_full:
                print(f"     FULL 獨有: {sorted(only_full)}")
            if only_min:
                print(f"     MINIMAL 獨有: {sorted(only_min)}")

    n = len(full["records"])
    print()
    print("=" * width)
    print("  摘要")
    print("=" * width)
    print(f"  遮罩結果一致: {match_count}/{n}")
    print()
    print(f"  {'指標':<32}{'FULL':>22}{'MINIMAL':>22}")
    print(f"  {'-'*76}")
    print(f"  {'初始化時間 (s)':<32}{full['init_time']:>22.2f}{minimal['init_time']:>22.2f}")
    print(f"  {'遮罩總時間 (s)':<32}{full['mask_time']:>22.2f}{minimal['mask_time']:>22.2f}")
    print(f"  {'平均每句 (ms)':<32}{full['mask_time']/n*1000:>22.1f}{minimal['mask_time']/n*1000:>22.1f}")
    print(f"  {'presidio+spacy 載入模組數':<32}{full['modules']:>22}{minimal['modules']:>22}")


def main():
    print("[1/2] 初始化 FULL pipeline（首次可能需下載 zh_core_web_sm + CKIP 模型）...")
    try:
        full = run_full(TEST_CASES)
    except Exception as e:
        print(f"[錯誤] FULL pipeline 初始化失敗：{e}")
        print("請確認已安裝：pip install -r requirements.txt 並 python -m spacy download zh_core_web_sm")
        return

    print("[2/2] 初始化 MINIMAL pipeline（CKIP 已有 cache，快）...")
    try:
        minimal = run_minimal(TEST_CASES)
    except Exception as e:
        print(f"[錯誤] MINIMAL pipeline 初始化失敗：{e}")
        return

    print_comparison(full, minimal)


if __name__ == "__main__":
    main()

"""
原始 pipeline vs pipeline_b 的遮罩效果比較。

A: original_file/pipeline.py — 原版 full pipeline
   (Presidio + spaCy zh_core_web_sm + 17 regex；含 normalizer、條件式 AMOUNT、
    speaker-aware boost、ConflictResolver、PseudonymTracker 編號 _1/_2/_3、Audit)

B: comparison/pipeline_b.py — 新版簡化 pipeline
   (CKIP + 20 純 regex；ConflictResolver；固定 token，無 normalizer / 無 pseudonym 編號)

用法：
  cd /Users/longxia/Documents/PII && python comparison/compare_original.py
"""
from __future__ import annotations

import pathlib
import sys
import time
import warnings
from typing import Any, Dict, List

warnings.filterwarnings("ignore")

_ROOT = pathlib.Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


# --- Presidio 版本 shim ---------------------------------------------------
# 原版 pipeline 寫成時 Presidio 允許 RecognizerRegistry() 不帶 supported_languages；
# 現版本要求 registry 與 AnalyzerEngine 的 supported_languages 一致，否則 ValueError。
# 為了在不改 original_file/ 內容的前提下跑起來，在此就地 patch。
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


def run_original(cases: List[str]) -> Dict[str, Any]:
    before = _loaded("presidio") + _loaded("spacy")
    from pipelines.a_original.pipeline import MaskingPipeline

    t0 = time.perf_counter()
    pipe = MaskingPipeline(log_path=None, score_threshold=0.50)
    init_time = time.perf_counter() - t0

    records = []
    t0 = time.perf_counter()
    for text in cases:
        res = pipe.mask(text=text, session_id="cmp")
        records.append({
            "original":   text,
            "normalized": res.normalized_text,
            "masked":     res.masked_text,
            "entities":   [
                (r.entity_type, res.normalized_text[r.start:r.end])
                for r in res.entities_found
            ],
            "conflicts":  len(res.conflict_log),
        })
    mask_time = time.perf_counter() - t0

    return {
        "label":     "A 原版 (Presidio+spaCy+17 regex+normalizer+pseudonym)",
        "init_time": init_time,
        "mask_time": mask_time,
        "records":   records,
        "modules":   _loaded("presidio") + _loaded("spacy") - before,
    }


def run_pipeline_b(cases: List[str]) -> Dict[str, Any]:
    before = _loaded("presidio") + _loaded("spacy")
    from pipelines.b_pure.pipeline import PipelineB

    t0 = time.perf_counter()
    pipe = PipelineB(with_ckip=True)
    init_time = time.perf_counter() - t0

    records = []
    t0 = time.perf_counter()
    for text in cases:
        masked, clean, log = pipe.mask(text)
        records.append({
            "original":   text,
            "normalized": text,
            "masked":     masked,
            "entities":   [(s.entity_type, text[s.start:s.end]) for s in clean],
            "conflicts":  len(log),
        })
    mask_time = time.perf_counter() - t0

    return {
        "label":     "B 新版 (CKIP+20 純 regex, no presidio/spacy runtime)",
        "init_time": init_time,
        "mask_time": mask_time,
        "records":   records,
        "modules":   _loaded("presidio") + _loaded("spacy") - before,
    }


def print_report(a: Dict[str, Any], b: Dict[str, Any]) -> None:
    width = 92
    print()
    print("=" * width)
    print(f"  {a['label']}")
    print(f"    vs")
    print(f"  {b['label']}")
    print("=" * width)

    match_count = 0
    ner_div = 0
    for ra, rb in zip(a["records"], b["records"]):
        same = ra["masked"] == rb["masked"]
        flag = "一致" if same else "差異"
        if same:
            match_count += 1
        print(f"\n[{flag}] 原文: {ra['original']}")
        if ra["normalized"] != ra["original"]:
            print(f"   A 正規化後: {ra['normalized']}")
        print(f"   A: {ra['masked']}   [{len(ra['entities'])} ent, {ra['conflicts']} 衝突]")
        print(f"   B: {rb['masked']}   [{len(rb['entities'])} ent, {rb['conflicts']} 衝突]")

        a_set = set(ra["entities"])
        b_set = set(rb["entities"])
        a_only = a_set - b_set
        b_only = b_set - a_set
        if a_only:
            print(f"     A 獨有實體: {sorted(a_only)}")
        if b_only:
            print(f"     B 獨有實體: {sorted(b_only)}")
        a_ner = {(t, v) for t, v in ra["entities"] if t in ("PERSON", "LOCATION")}
        b_ner = {(t, v) for t, v in rb["entities"] if t in ("PERSON", "LOCATION")}
        if a_ner != b_ner:
            ner_div += 1

    n = len(a["records"])
    print()
    print("=" * width)
    print("  摘要")
    print("=" * width)
    print(f"  遮罩一致: {match_count}/{n}   NER 差異案例: {ner_div}/{n}")
    print()
    print(f"  {'指標':<34}{'A 原版':>26}{'B 新版':>26}")
    print(f"  {'-'*86}")
    print(f"  {'初始化時間 (s)':<34}{a['init_time']:>26.2f}{b['init_time']:>26.2f}")
    print(f"  {'遮罩總時間 (s)':<34}{a['mask_time']:>26.2f}{b['mask_time']:>26.2f}")
    print(f"  {'平均每句 (ms)':<34}{a['mask_time']/n*1000:>26.1f}{b['mask_time']/n*1000:>26.1f}")
    print(f"  {'runtime 新增 presidio+spacy 模組':<34}{a['modules']:>26}{b['modules']:>26}")


def main():
    print("[A 原版] 初始化 Presidio + spaCy + 17 regex ...", flush=True)
    try:
        a = run_original(TEST_CASES)
    except Exception as e:
        print(f"[錯誤] A 初始化或執行失敗：{type(e).__name__}: {e}")
        import traceback; traceback.print_exc()
        return
    print(f"  A 完成：init={a['init_time']:.2f}s, mask={a['mask_time']:.2f}s", flush=True)

    print("[B 新版] 初始化 CKIP + 20 pure regex ...", flush=True)
    try:
        b = run_pipeline_b(TEST_CASES)
    except Exception as e:
        print(f"[錯誤] B 初始化或執行失敗：{type(e).__name__}: {e}")
        import traceback; traceback.print_exc()
        return
    print(f"  B 完成：init={b['init_time']:.2f}s, mask={b['mask_time']:.2f}s", flush=True)

    print_report(a, b)


if __name__ == "__main__":
    main()

"""
Minimal POC — PII masking pipeline WITHOUT Presidio + spaCy.

依賴：ckip-transformers, torch（僅此兩項；不再需要 presidio-analyzer / spacy / zh_core_web_sm）

證明：
  1. 移除 Presidio/spaCy 後，CKIP + regex + ConflictResolver 仍可完成遮罩
  2. ConflictResolver 透過 duck-typing 接受本地 `Span` dataclass（不依賴 presidio 型別）
  3. 結構性衝突（數字類撞類、巢狀地址）依然存在 — 證明 resolver 不是 Presidio 強加的

用法：python minimal_pipeline.py
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List, Optional, Tuple


# ══════════════════════════════════════════════════════════════
# 1. 資料型別（取代 Presidio 的 RecognizerResult / AnalysisExplanation）
# ══════════════════════════════════════════════════════════════

@dataclass
class Explanation:
    recognizer: str = ""
    pattern_name: Optional[str] = None
    score_context_improvement: float = 0.0
    supportive_context_word: Optional[str] = None


@dataclass
class Span:
    """
    Duck-compatible 與 Presidio 的 RecognizerResult 介面。
    ConflictResolver 只透過 .entity_type / .start / .end / .score /
    .analysis_explanation 存取，不關心物件型別。
    """
    entity_type: str
    start: int
    end: int
    score: float
    analysis_explanation: Optional[Explanation] = None


# ══════════════════════════════════════════════════════════════
# 2. Recognizer 基底 + 實作（純 regex，無 Presidio 相依）
# ══════════════════════════════════════════════════════════════

class Recognizer:
    name: str = ""
    def analyze(self, text: str) -> List[Span]:
        raise NotImplementedError


class TWPhoneRecognizer(Recognizer):
    name = "TWPhone"
    PATTERNS = [
        ("MOBILE",   re.compile(r"09\d{8}"),       0.90),
        ("LANDLINE", re.compile(r"0[2-8]\d{7,8}"), 0.85),
    ]
    def analyze(self, text):
        return [
            Span("TW_PHONE", m.start(), m.end(), score,
                 Explanation(self.name, pname))
            for pname, pat, score in self.PATTERNS
            for m in pat.finditer(text)
        ]


class TWCreditCardRecognizer(Recognizer):
    name = "TWCreditCard"
    PAT = re.compile(r"(?<!\d)\d{13,19}(?!\d)")
    def analyze(self, text):
        return [
            Span("TW_CREDIT_CARD", m.start(), m.end(), 0.90,
                 Explanation(self.name, "CREDIT_CARD"))
            for m in self.PAT.finditer(text)
        ]


class TWBankAccountRecognizer(Recognizer):
    name = "TWBankAccount"
    PAT = re.compile(r"(?<!\d)\d{12,16}(?!\d)")
    def analyze(self, text):
        return [
            Span("TW_BANK_ACCOUNT", m.start(), m.end(), 0.85,
                 Explanation(self.name, "ACCOUNT"))
            for m in self.PAT.finditer(text)
        ]


class OTPRecognizer(Recognizer):
    """Context-aware：前 20 字內需有關鍵字才觸發。"""
    name = "OTP"
    PAT = re.compile(r"(?<!\d)\d{4,8}(?!\d)")
    KEYWORDS = ["驗證碼", "OTP", "一次性密碼"]
    def analyze(self, text):
        out: List[Span] = []
        for m in self.PAT.finditer(text):
            ctx = text[max(0, m.start() - 20):m.start()]
            kw = next((k for k in self.KEYWORDS if k in ctx), None)
            if kw:
                out.append(Span(
                    "OTP", m.start(), m.end(), 0.85,
                    Explanation(self.name, "OTP",
                                score_context_improvement=0.3,
                                supportive_context_word=kw),
                ))
        return out


class AddressRegexRecognizer(Recognizer):
    """簡化版地址：縣市 + 路/街 + 號。整段偵測為 LOCATION。"""
    name = "AddressRegex"
    PAT = re.compile(
        r"(?:台北|新北|桃園|台中|台南|高雄)(?:市|縣)"
        r"[\u4e00-\u9fff]{2,10}(?:路|街|道)"
        r"\d{1,4}(?:號|巷|弄)?"
    )
    def analyze(self, text):
        return [
            Span("LOCATION", m.start(), m.end(), 0.88,
                 Explanation(self.name, "ADDRESS_FULL"))
            for m in self.PAT.finditer(text)
        ]


class CKIPNer(Recognizer):
    """CKIP Transformers — 純 wrapper，不繼承 Presidio。"""
    name = "CKIP"
    _TAG_MAP = {"PERSON": "PERSON", "GPE": "LOCATION", "LOC": "LOCATION"}

    def __init__(self, model: str = "bert-base", device: int = -1):
        from ckip_transformers.nlp import CkipNerChunker
        self._driver = CkipNerChunker(model=model, device=device)

    def analyze(self, text):
        if not text.strip():
            return []
        ner = self._driver([text], use_delim=False, show_progress=False)
        if not ner or not ner[0]:
            return []
        out: List[Span] = []
        for tok in ner[0]:
            etype = self._TAG_MAP.get(tok.ner)
            if etype is None:
                continue
            out.append(Span(
                etype, tok.idx[0], tok.idx[1], 0.85,
                Explanation(self.name, f"CKIP_{tok.ner}"),
            ))
        return out


# ══════════════════════════════════════════════════════════════
# 3. Pipeline：直接 for-loop orchestrate + 共用原 ConflictResolver
#    （resolver 不依賴 Presidio，只讀 duck-typed 欄位）
# ══════════════════════════════════════════════════════════════

from conflict_resolver import ConflictResolver

TOKEN_MAP = {
    "TW_PHONE":        "[PHONE]",
    "TW_CREDIT_CARD":  "[CARD]",
    "TW_BANK_ACCOUNT": "[ACCOUNT]",
    "OTP":             "[OTP]",
    "PERSON":          "[NAME]",
    "LOCATION":        "[ADDRESS]",
}


class MinimalPipeline:
    def __init__(self, with_ckip: bool = True):
        self.recognizers: List[Recognizer] = [
            TWPhoneRecognizer(),
            TWCreditCardRecognizer(),
            TWBankAccountRecognizer(),
            OTPRecognizer(),
            AddressRegexRecognizer(),
        ]
        if with_ckip:
            self.recognizers.append(CKIPNer())
        self.resolver = ConflictResolver()

    def mask(self, text: str) -> Tuple[str, List[Span], list]:
        raw: List[Span] = []
        for rec in self.recognizers:
            raw.extend(rec.analyze(text))
        clean, log = self.resolver.resolve(raw, text)
        masked = text
        for r in sorted(clean, key=lambda s: s.start, reverse=True):
            token = TOKEN_MAP.get(r.entity_type, f"[{r.entity_type}]")
            masked = masked[:r.start] + token + masked[r.end:]
        return masked, clean, log


# ══════════════════════════════════════════════════════════════
# 4. Demo + 確認沒載入 Presidio/spaCy
# ══════════════════════════════════════════════════════════════

def demo():
    import sys
    loaded = {m for m in sys.modules if m.startswith(("presidio", "spacy"))}
    print("=" * 60)
    print(" Minimal Pipeline POC — CKIP + regex only")
    print("=" * 60)
    print(f"載入前 presidio/spacy modules: {loaded or '無'}")

    pipeline = MinimalPipeline(with_ckip=True)

    loaded_after = {m for m in sys.modules if m.startswith(("presidio", "spacy"))}
    print(f"初始化後 presidio/spacy modules: {loaded_after or '無'}")
    print()

    cases = [
        "我叫王小明，卡號是1234567890123456",
        "我電話0912345678",
        "住在台北市忠孝東路100號",
        "驗證碼是654321",
        "轉帳到帳號123456789012",
        "我家住在好市多隔壁的SEVEN樓上"
    ]
    for text in cases:
        masked, clean, log = pipeline.mask(text)
        print(f"原文: {text}")
        print(f"遮罩: {masked}")
        ents = ", ".join(f"{s.entity_type}({text[s.start:s.end]})" for s in clean)
        print(f"實體: [{ents}]")
        if log:
            for entry in log:
                w, l, reason = entry
                print(f"  衝突: {w.entity_type} 勝 {l.entity_type} | {reason}")
        print()


if __name__ == "__main__":
    demo()

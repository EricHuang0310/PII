"""
Pipeline C：以 pipeline_b 為骨幹，合併原版 pipeline 的
  - normalizer（全形/民國/STT filler 壓縮）
  - PseudonymTracker（同值一致、_1/_2 編號）
  - bank rules（條件式 AMOUNT + speaker-aware fallback boost）

Runtime 同樣不 import presidio / spacy。
"""
from __future__ import annotations

import copy
import re
from typing import Dict, List, Optional, Set, Tuple

from pipelines.b_pure.ckip_wrap import CKIPNer
from pipelines.b_pure.pure_recognizers import Recognizer, get_pure_recognizers
from pipelines.b_pure.span import Span
from conflict_resolver import ConflictResolver

# normalize() 與 PseudonymTracker 直接重用 a_original 的實作
from pipelines.a_original.normalizer import normalize
from pipelines.a_original.pseudonym import PseudonymTracker


TOKEN_MAP = {
    "TW_PHONE":             "[PHONE]",
    "TW_ID_NUMBER":         "[ID]",
    "PASSPORT":             "[PASSPORT]",
    "DOB":                  "[DOB]",
    "TW_CREDIT_CARD":       "[CARD]",
    "TW_BANK_ACCOUNT":      "[ACCOUNT]",
    "ATM_REF":              "[ATM_REF]",
    "LOAN_REF":             "[LOAN_REF]",
    "TXN_REF":              "[TXN_REF]",
    "POLICY_NO":            "[POLICY_NO]",
    "AMOUNT":               "[AMOUNT]",
    "AMOUNT_TXN":           "[AMOUNT_TXN]",
    "OTP":                  "[OTP]",
    "CVV":                  "[CVV]",
    "EXPIRY":               "[EXPIRY]",
    "PIN":                  "[PIN]",
    "LOCATION":             "[ADDRESS]",
    "STAFF_ID":             "[STAFF_ID]",
    "CAMPAIGN":             "[CAMPAIGN]",
    "BRANCH":               "[BRANCH]",
    "VERIFICATION_ANSWER":  "[VERIFICATION_ANSWER]",
    "PERSON":               "[NAME]",
    "EMAIL_ADDRESS":        "[EMAIL]",
}

AMOUNT_TRIGGER_ENTITIES: Set[str] = {"TW_BANK_ACCOUNT", "TW_CREDIT_CARD"}
AMOUNT_PROXIMITY_CHARS: int       = 60
FALLBACK_ANSWER_WINDOW_CHARS: int = 30

AGENT_QUESTION_PATTERNS = [
    r"請問您的.{0,15}[是為]",
    r"請問您.{0,10}[嗎？?]",
    r"可以.{0,8}嗎",
    r"需要.{0,6}驗證",
    r"確認一下您的",
    r"報一下您的",
    r"幫我.{0,6}確認",
]
ANSWER_PATTERNS = [
    r"是\s*\d{4,16}",
    r"我的.{0,6}是\s*\d",
    r"對[，。,.]?\s*\d",
    r"^\d{4,16}$",
    r"[\u4e00-\u9fff]{2,4}(?=[，。,.\s]|$)",
]

PSEUDONYM_ENTITIES: Set[str] = {
    "PERSON", "TW_CREDIT_CARD", "TW_BANK_ACCOUNT",
    "TXN_REF", "ATM_REF", "LOAN_REF",
}


class PipelineC:
    """B 骨幹 + normalizer + PseudonymTracker + bank rules。"""

    def __init__(self, with_ckip: bool = True):
        self.recognizers: List[Recognizer] = list(get_pure_recognizers())
        if with_ckip:
            self.recognizers.append(CKIPNer())
        self.resolver = ConflictResolver()
        self._agent_q = re.compile("|".join(AGENT_QUESTION_PATTERNS))
        self._answers = [re.compile(p) for p in ANSWER_PATTERNS]

    def _apply_conditional_amount(self, text: str, results: List[Span]) -> List[Span]:
        amounts  = [r for r in results if r.entity_type == "AMOUNT"]
        triggers = [r for r in results if r.entity_type in AMOUNT_TRIGGER_ENTITIES]
        if not triggers:
            return [r for r in results if r.entity_type != "AMOUNT"]
        keep_ids: Set[int] = set()
        for ar in amounts:
            if any(abs(ar.start - tr.start) <= AMOUNT_PROXIMITY_CHARS for tr in triggers):
                keep_ids.add(id(ar))
        return [r for r in results if r.entity_type != "AMOUNT" or id(r) in keep_ids]

    def _apply_speaker_boost(self, text: str, results: List[Span],
                             diarization_available: bool) -> List[Span]:
        if diarization_available:
            return results
        q_boost: Dict[int, float] = {}
        a_boost: Dict[int, float] = {}
        for qm in self._agent_q.finditer(text):
            win_end = qm.end() + FALLBACK_ANSWER_WINDOW_CHARS
            for r in results:
                if qm.end() <= r.start <= win_end:
                    q_boost[id(r)] = max(q_boost.get(id(r), 0.0), 0.15)
        for ap in self._answers:
            for am in ap.finditer(text):
                for r in results:
                    if am.start() <= r.start < am.end():
                        a_boost[id(r)] = max(a_boost.get(id(r), 0.0), 0.10)
        out: List[Span] = []
        for r in results:
            total = q_boost.get(id(r), 0.0) + a_boost.get(id(r), 0.0)
            if total > 0.0:
                nr = copy.copy(r)
                nr.score = min(1.0, r.score + total)
                out.append(nr)
            else:
                out.append(r)
        return out

    def mask(self, text: str,
             session_id: str = "",
             diarization_available: bool = False,
             tracker: Optional[PseudonymTracker] = None
             ) -> Tuple[str, str, List[Span], list, Dict]:
        normalized = normalize(text)

        raw: List[Span] = []
        for rec in self.recognizers:
            raw.extend(rec.analyze(normalized))

        raw = self._apply_conditional_amount(normalized, raw)
        raw = self._apply_speaker_boost(normalized, raw, diarization_available)

        clean, log = self.resolver.resolve(raw, normalized)

        if tracker is None:
            tracker = PseudonymTracker(session_id=session_id,
                                       pseudonym_entities=PSEUDONYM_ENTITIES)

        token_of: Dict[int, str] = {}
        for r in clean:
            base = TOKEN_MAP.get(r.entity_type, f"[{r.entity_type}]")
            original_value = normalized[r.start:r.end]
            token_of[id(r)] = tracker.resolve(r.entity_type, original_value, base)

        masked = normalized
        for r in sorted(clean, key=lambda s: s.start, reverse=True):
            tok = token_of[id(r)]
            masked = masked[:r.start] + tok + masked[r.end:]

        return normalized, masked, clean, log, tracker.get_mapping()

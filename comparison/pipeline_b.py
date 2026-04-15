"""
B 側 pipeline：CKIP + 20 純 regex recognizer。
Runtime 不 import presidio / spacy。
"""
from __future__ import annotations

from typing import List, Tuple

from comparison.ckip_wrap import CKIPNer
from comparison.pure_recognizers import Recognizer, get_pure_recognizers
from comparison.span import Span
from conflict_resolver import ConflictResolver   # duck-typed；resolver 已解除 presidio runtime 相依


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


class PipelineB:
    """CKIP + 20 pure regex，無 presidio / spacy。"""

    def __init__(self, with_ckip: bool = True):
        self.recognizers: List[Recognizer] = list(get_pure_recognizers())
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

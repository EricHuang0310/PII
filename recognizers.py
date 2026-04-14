# masking/recognizers.py  v3
import re
from typing import List, Optional
from presidio_analyzer import (
    PatternRecognizer, Pattern, RecognizerResult,
    EntityRecognizer, AnalysisExplanation,
)
from presidio_analyzer.nlp_engine import NlpArtifacts
from config import (
    PHONE_CONTEXT, ID_CONTEXT, CREDIT_CARD_CONTEXT, BANK_ACCOUNT_CONTEXT,
    OTP_CONTEXT, CVV_CONTEXT, EXPIRY_CONTEXT, PIN_CONTEXT, DOB_CONTEXT,
    AMOUNT_CONTEXT, STAFF_ID_CONTEXT, PASSPORT_CONTEXT, LOAN_CONTEXT,
    TXN_CONTEXT, ATM_CONTEXT, CAMPAIGN_CONTEXT, VERIFICATION_CONTEXT,
    POLICY_CONTEXT, BRANCH_CONTEXT,
    HIGH_RISK_TXN_VERBS, ADMIN_DISTRICTS, CHAIN_LANDMARKS,
    LANDMARK_SUFFIX_PATTERN, PROXIMITY_PATTERN, FALLBACK_ANSWER_WINDOW_CHARS,
)

class TWPhoneRecognizer(PatternRecognizer):
    PATTERNS = [
        Pattern("MOBILE",   r"09\d{8}",       score=0.85),
        Pattern("LANDLINE", r"0[2-8]\d{7,8}", score=0.75),
    ]
    def __init__(self):
        super().__init__(supported_entity="TW_PHONE", patterns=self.PATTERNS, context=PHONE_CONTEXT, supported_language="zh")

class TWIDRecognizer(PatternRecognizer):
    PATTERNS = [Pattern("TW_ID", r"[A-Za-z][12]\d{8}", score=0.90)]
    def __init__(self):
        super().__init__(supported_entity="TW_ID_NUMBER", patterns=self.PATTERNS, context=ID_CONTEXT, supported_language="zh")

class PassportRecognizer(PatternRecognizer):
    PATTERNS = [Pattern("PASSPORT", r"[A-Z]{1,2}\d{7,9}", score=0.70)]
    def __init__(self):
        super().__init__(supported_entity="PASSPORT", patterns=self.PATTERNS, context=PASSPORT_CONTEXT, supported_language="zh")

class DOBRecognizer(PatternRecognizer):
    PATTERNS = [
        Pattern("DOB_8",     r"\d{8}",                    score=0.50),
        Pattern("DOB_SLASH", r"\d{4}[/-]\d{2}[/-]\d{2}", score=0.70),
    ]
    def __init__(self):
        super().__init__(supported_entity="DOB", patterns=self.PATTERNS, context=DOB_CONTEXT, supported_language="zh")

class TWCreditCardRecognizer(PatternRecognizer):
    PATTERNS = [Pattern("CC_16", r"\d{16}", score=0.55)]
    def __init__(self):
        super().__init__(supported_entity="TW_CREDIT_CARD", patterns=self.PATTERNS, context=CREDIT_CARD_CONTEXT, supported_language="zh")

class TWBankAccountRecognizer(PatternRecognizer):
    PATTERNS = [Pattern("BANK_ACCT", r"(?!09\d{8})\d{10,14}", score=0.50)]
    def __init__(self):
        super().__init__(supported_entity="TW_BANK_ACCOUNT", patterns=self.PATTERNS, context=BANK_ACCOUNT_CONTEXT, supported_language="zh")

class ATMRefRecognizer(PatternRecognizer):
    PATTERNS = [Pattern("ATM_REF", r"\d{8,20}", score=0.40)]
    def __init__(self):
        super().__init__(supported_entity="ATM_REF", patterns=self.PATTERNS, context=ATM_CONTEXT, supported_language="zh")

class LoanRefRecognizer(PatternRecognizer):
    PATTERNS = [
        Pattern("LOAN_REF_NUM",   r"\d{8,15}",          score=0.45),
        Pattern("LOAN_REF_ALPHA", r"[A-Z]{1,3}\d{6,12}", score=0.65),
    ]
    def __init__(self):
        super().__init__(supported_entity="LOAN_REF", patterns=self.PATTERNS, context=LOAN_CONTEXT, supported_language="zh")

class TXNRefRecognizer(PatternRecognizer):
    PATTERNS = [
        Pattern("TXN_NUM",   r"\d{8,20}",           score=0.40),
        Pattern("TXN_ALPHA", r"[A-Z]{1,3}\d{8,15}", score=0.60),
    ]
    def __init__(self):
        super().__init__(supported_entity="TXN_REF", patterns=self.PATTERNS, context=TXN_CONTEXT, supported_language="zh")

class PolicyNoRecognizer(PatternRecognizer):
    PATTERNS = [
        Pattern("POLICY_ALPHA", r"[A-Z]\d{6,12}", score=0.60),
        Pattern("POLICY_NUM",   r"P\d{6,10}",     score=0.75),
    ]
    def __init__(self):
        super().__init__(supported_entity="POLICY_NO", patterns=self.PATTERNS, context=POLICY_CONTEXT, supported_language="zh")

class AmountRecognizer(PatternRecognizer):
    PATTERNS = [
        Pattern("AMOUNT_YUAN", r"\d+(?:,\d{3})*元",       score=0.80),
        Pattern("AMOUNT_KUAI", r"\d+(?:,\d{3})*塊",       score=0.75),
        Pattern("AMOUNT_NT",   r"NT\$?\s*\d+(?:,\d{3})*", score=0.80),
        Pattern("AMOUNT_NUM",  r"\d+(?:,\d{3})*",         score=0.40),
    ]
    def __init__(self):
        super().__init__(supported_entity="AMOUNT", patterns=self.PATTERNS, context=AMOUNT_CONTEXT, supported_language="zh")

class AmountTxnRecognizer(EntityRecognizer):
    """v3: 高風險交易金額（交易動詞觸發，無需帳號並存）"""
    _VERB_RE = re.compile(
        "(?:" + "|".join(re.escape(v) for v in HIGH_RISK_TXN_VERBS) + ")"
        r".{0,20}?(\d+(?:,\d{3})*(?:元|塊|NTD|NT)?)"
        r"|(\d+(?:,\d{3})*(?:元|塊|NTD|NT)?).{0,10}?"
        "(?:" + "|".join(re.escape(v) for v in HIGH_RISK_TXN_VERBS) + ")"
    )
    def __init__(self):
        super().__init__(supported_entities=["AMOUNT_TXN"], supported_language="zh")
    def load(self): pass
    def analyze(self, text, entities, nlp_artifacts=None):
        results = []
        for m in self._VERB_RE.finditer(text):
            num = m.group(1) or m.group(2)
            if not num: continue
            idx = text.find(num, m.start())
            if idx == -1: continue
            results.append(RecognizerResult(
                entity_type="AMOUNT_TXN", start=idx, end=idx+len(num), score=0.82,
                analysis_explanation=AnalysisExplanation(
                    recognizer=self.__class__.__name__, original_score=0.82,
                    pattern_name="AMOUNT_TXN_VERB", pattern=m.group(0)[:50], validation_result=None,
                ),
            ))
        return results

class OTPRecognizer(PatternRecognizer):
    PATTERNS = [Pattern("OTP_6", r"\d{6}", score=0.5)]
    def __init__(self):
        super().__init__(supported_entity="OTP", patterns=self.PATTERNS, context=OTP_CONTEXT, supported_language="zh")

class CVVRecognizer(PatternRecognizer):
    PATTERNS = [Pattern("CVV_3", r"\d{3}", score=0.30)]
    def __init__(self):
        super().__init__(supported_entity="CVV", patterns=self.PATTERNS, context=CVV_CONTEXT, supported_language="zh")

class ExpiryRecognizer(PatternRecognizer):
    PATTERNS = [
        Pattern("EXPIRY_MMYY",  r"(?:0[1-9]|1[0-2])\d{2}",  score=0.45),
        Pattern("EXPIRY_SLASH", r"(?:0[1-9]|1[0-2])/\d{2}", score=0.65),
    ]
    def __init__(self):
        super().__init__(supported_entity="EXPIRY", patterns=self.PATTERNS, context=EXPIRY_CONTEXT, supported_language="zh")

class PINRecognizer(PatternRecognizer):
    PATTERNS = [Pattern("PIN_46", r"\d{4,6}", score=0.30)]
    def __init__(self):
        super().__init__(supported_entity="PIN", patterns=self.PATTERNS, context=PIN_CONTEXT, supported_language="zh")

class AddressEnhancedRecognizer(EntityRecognizer):
    """v3: 地址三層偵測"""
    _L1 = re.compile(
        "(?:" + "|".join(re.escape(d) for d in ADMIN_DISTRICTS) + ")"
        r"[\u4e00-\u9fff]{0,15}?"           # 區/里/鄰等
        r"(?:路|街|大道)"                     # 路名結尾
        r"(?:[\u4e00-\u9fff]?段)?"           # 段（一段、二段）
        r"(?:\d{1,4}巷)?"                    # 巷
        r"(?:\d{1,4}弄)?"                    # 弄
        r"(?:\d{1,4}號)?"                    # 號
        r"(?:\d{1,3}樓)?"                    # 樓
        r"(?:之\d{1,3})?"                    # 之X
    )
    _L2 = re.compile("(?:" + "|".join(re.escape(c) for c in CHAIN_LANDMARKS) + r").{0,4}(?:店|門市|分店|賣場)?")
    _L3_LM = re.compile(LANDMARK_SUFFIX_PATTERN)
    _L3_PX = re.compile(PROXIMITY_PATTERN)

    def __init__(self):
        super().__init__(supported_entities=["LOCATION"], supported_language="zh")
    def load(self): pass
    def analyze(self, text, entities, nlp_artifacts=None):
        results = []
        def _add(m, score, layer):
            results.append(RecognizerResult(
                entity_type="LOCATION", start=m.start(), end=m.end(), score=score,
                analysis_explanation=AnalysisExplanation(
                    recognizer=self.__class__.__name__, original_score=score,
                    pattern_name=layer, pattern=m.group(0)[:40], validation_result=None,
                ),
            ))
        for m in self._L1.finditer(text):   _add(m, 0.85, "ADDR_L1_ADMIN")
        for m in self._L2.finditer(text):   _add(m, 0.75, "ADDR_L2_CHAIN")
        for m in self._L3_LM.finditer(text):_add(m, 0.70, "ADDR_L3_LANDMARK")
        for m in self._L3_PX.finditer(text):_add(m, 0.72, "ADDR_L3_PROXIMITY")
        return results

class StaffIDRecognizer(PatternRecognizer):
    PATTERNS = [
        Pattern("STAFF_ALPHA",  r"[A-Z]\d{4,8}",             score=0.55),
        Pattern("STAFF_PREFIX", r"(?:EMP|STAFF|E|A)\d{4,8}", score=0.70),
    ]
    def __init__(self):
        super().__init__(supported_entity="STAFF_ID", patterns=self.PATTERNS, context=STAFF_ID_CONTEXT, supported_language="zh")

class CampaignRecognizer(PatternRecognizer):
    PATTERNS = [Pattern("CAMPAIGN_CODE", r"[A-Z]{2,4}\d{3,6}", score=0.50)]
    def __init__(self):
        super().__init__(supported_entity="CAMPAIGN", patterns=self.PATTERNS, context=CAMPAIGN_CONTEXT, supported_language="zh")

class BranchRecognizer(PatternRecognizer):
    PATTERNS = [
        Pattern("BRANCH_NUM",   r"\d{3,4}",           score=0.35),
        Pattern("BRANCH_ALPHA", r"[A-Z]{2,4}\d{2,4}", score=0.55),
    ]
    def __init__(self):
        super().__init__(supported_entity="BRANCH", patterns=self.PATTERNS, context=BRANCH_CONTEXT, supported_language="zh")

class VerificationAnswerRecognizer(EntityRecognizer):
    def __init__(self):
        super().__init__(supported_entities=["VERIFICATION_ANSWER"], supported_language="zh")
        self._trigger = re.compile("|".join(re.escape(kw) for kw in VERIFICATION_CONTEXT))
        self._answer  = re.compile(r"\d{6,8}")
    def load(self): pass
    def analyze(self, text, entities, nlp_artifacts=None):
        results = []
        for tm in self._trigger.finditer(text):
            ws, we = tm.end(), min(len(text), tm.end() + FALLBACK_ANSWER_WINDOW_CHARS)
            for am in self._answer.finditer(text[ws:we]):
                results.append(RecognizerResult(
                    entity_type="VERIFICATION_ANSWER", start=ws+am.start(), end=ws+am.end(), score=0.75,
                    analysis_explanation=AnalysisExplanation(
                        recognizer=self.__class__.__name__, original_score=0.75,
                        pattern_name="VERIFICATION_TRIGGER", pattern=tm.group(0), validation_result=None,
                    ),
                ))
        return results

def get_all_custom_recognizers(ckip_model="bert-base", ckip_device=-1):
    """
    回傳所有 custom recognizer。

    v4 變更：CKIP Transformers NER 為必要組件（負責中文 PERSON / LOCATION
    偵測），永遠註冊至 AnalyzerEngine。首次執行時會下載並載入模型，需事先
    安裝 `ckip-transformers` 與 `torch`。
    """
    from ckip_recognizer import CkipNerRecognizer

    return [
        TWPhoneRecognizer(), TWIDRecognizer(), PassportRecognizer(), DOBRecognizer(),
        TWCreditCardRecognizer(), TWBankAccountRecognizer(), ATMRefRecognizer(),
        LoanRefRecognizer(), TXNRefRecognizer(), PolicyNoRecognizer(),
        AmountRecognizer(), AmountTxnRecognizer(),
        OTPRecognizer(), CVVRecognizer(), ExpiryRecognizer(), PINRecognizer(),
        AddressEnhancedRecognizer(),
        StaffIDRecognizer(), CampaignRecognizer(), BranchRecognizer(),
        VerificationAnswerRecognizer(),
        CkipNerRecognizer(model=ckip_model, device=ckip_device),
    ]

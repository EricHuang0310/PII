"""
20 個純 regex recognizer（port 自 recognizers.py，無 presidio/spacy 依賴）。

類型：
  - 18 個 PatternRecognizer 子類 → 透過 PurePatternRecognizer 工廠化產生
  - 3 個自訂邏輯（AmountTxn / AddressEnhanced / VerificationAnswer）→ 各自獨立 class

Context boost 行為模擬 Presidio：
  - 對每個 regex match，檢查 ±_CONTEXT_WINDOW 字內是否出現 context 關鍵字
  - 命中則 score += _CONTEXT_BOOST（上限 1.0），並設定
    Explanation.score_context_improvement 與 supportive_context_word
    （讓 conflict_resolver._has_keyword_context 能正確判定）
"""
from __future__ import annotations

import re
from typing import List, Optional, Tuple

from comparison.span import Span, Explanation


_CONTEXT_WINDOW = 30
_CONTEXT_BOOST  = 0.35


class Recognizer:
    name: str = ""
    def analyze(self, text: str) -> List[Span]:
        raise NotImplementedError


class PurePatternRecognizer(Recognizer):
    """固定介面：regex + context window boost。"""

    def __init__(self, entity_type: str,
                 patterns: List[Tuple[str, str, float]],
                 context_keywords: List[str]):
        self.entity_type = entity_type
        self.compiled = [(name, re.compile(pat), score)
                         for name, pat, score in patterns]
        self.context_keywords = context_keywords
        self.name = f"Pure_{entity_type}"

    def _find_context_word(self, text: str, start: int, end: int) -> Optional[str]:
        w_start = max(0, start - _CONTEXT_WINDOW)
        w_end = min(len(text), end + _CONTEXT_WINDOW)
        window = text[w_start:w_end]
        for kw in self.context_keywords:
            if kw in window:
                return kw
        return None

    def analyze(self, text: str) -> List[Span]:
        results: List[Span] = []
        for pat_name, regex, base_score in self.compiled:
            for m in regex.finditer(text):
                kw = self._find_context_word(text, m.start(), m.end())
                score = min(1.0, base_score + _CONTEXT_BOOST) if kw else base_score
                exp = Explanation(
                    recognizer=self.name,
                    pattern_name=pat_name,
                    score_context_improvement=_CONTEXT_BOOST if kw else 0.0,
                    supportive_context_word=kw,
                )
                results.append(Span(self.entity_type, m.start(), m.end(), score, exp))
        return results


# ══════════════════════════════════════════════════════════════
# Context 關鍵字（複製自 config.py，保持 B 側完全自足）
# ══════════════════════════════════════════════════════════════
_PHONE_CONTEXT    = ["電話", "手機", "市話", "聯絡", "號碼", "撥打", "回撥", "致電", "phone", "mobile"]
_ID_CONTEXT       = ["身分證", "身份證", "證號", "ID", "字號"]
_CC_CONTEXT       = ["卡號", "信用卡", "卡", "刷卡", "card", "credit"]
_BANK_CONTEXT     = ["帳號", "帳戶", "轉帳", "匯款", "存款", "account", "acct"]
_OTP_CONTEXT      = ["驗證碼", "一次性密碼", "OTP", "簡訊碼", "認證碼", "動態密碼"]
_CVV_CONTEXT      = ["背面三碼", "安全碼", "CVV", "CVC", "末三碼"]
_EXPIRY_CONTEXT   = ["有效期限", "到期", "效期", "expiry", "expiration", "valid"]
_PIN_CONTEXT      = ["密碼", "PIN", "網銀密碼", "提款密碼", "交易密碼"]
_DOB_CONTEXT      = ["生日", "出生", "生年月日", "birthday", "birth", "出生日期"]
_HIGH_RISK_VERBS  = ["轉帳", "匯款", "扣款", "刷卡", "付款", "繳費", "提款", "存款",
                     "匯入", "撥款", "退款", "退費", "交易", "扣繳", "扣除", "入帳", "出帳"]
_AMOUNT_CONTEXT   = ["元", "塊", "錢", "金額", "餘額", "NT", "NTD"] + _HIGH_RISK_VERBS
_STAFF_CONTEXT    = ["工號", "員工編號", "行員", "客服代號", "staff", "employee"]
_PASSPORT_CONTEXT = ["護照", "passport"]
_LOAN_CONTEXT     = ["貸款", "合約號", "借款", "loan", "合約"]
_TXN_CONTEXT      = ["交易", "流水號", "序號", "transaction", "txn", "ref"]
_ATM_CONTEXT      = ["ATM", "交易序號", "自動提款", "參考號碼"]
_CAMPAIGN_CONTEXT = ["活動", "專案", "行銷", "campaign", "promo"]
_VERIFICATION     = ["母親", "媽媽", "驗證問題", "安全問題", "母親姓名", "母親生日"]
_POLICY_CONTEXT   = ["保單", "保險單", "policy", "投保"]
_BRANCH_CONTEXT   = ["分行", "分行代碼", "branch", "分店"]
_EMAIL_CONTEXT    = ["email", "e-mail", "信箱", "電子郵件", "郵件", "mail"]


# ══════════════════════════════════════════════════════════════
# Address 三層偵測用詞庫 / pattern（複製自 config.py）
# ══════════════════════════════════════════════════════════════
_ADMIN_DISTRICTS = [
    "台北市", "臺北市", "新北市", "桃園市", "台中市", "臺中市",
    "台南市", "臺南市", "高雄市", "基隆市", "新竹市", "嘉義市",
    "新竹縣", "苗栗縣", "彰化縣", "南投縣", "雲林縣", "嘉義縣",
    "屏東縣", "宜蘭縣", "花蓮縣", "台東縣", "臺東縣",
    "澎湖縣", "金門縣", "連江縣",
    "中和", "板橋", "新店", "永和", "三重", "蘆洲", "汐止",
    "土城", "樹林", "鶯歌", "三峽", "淡水", "林口", "泰山",
    "五股", "新莊", "中壢", "平鎮", "八德", "楊梅", "大溪",
    "左營", "鳳山", "三民", "苓雅", "前鎮", "小港",
    "北屯", "西屯", "南屯", "太平", "大里", "霧峰",
]

_CHAIN_LANDMARKS = [
    "Costco", "costco", "好市多",
    "SOGO", "sogo", "太平洋",
    "家樂福", "大潤發", "全聯", "頂好", "愛買",
    "IKEA", "ikea",
    "麥當勞", "肯德基", "摩斯漢堡",
    "星巴克", "路易莎",
    "新光三越", "微風", "遠東百貨", "漢神", "統一阪急",
    "台鐵", "高鐵", "捷運",
]

_LANDMARK_SUFFIX = (
    r"[\u4e00-\u9fff]{2,6}"
    r"(?:國小|國中|高中|大學|醫院|診所|公園|廟|宮|"
    r"捷運站|火車站|高鐵站|客運站|機場|"
    r"夜市|市場|商圈|購物中心|廣場)"
)

_PROXIMITY = (
    r"(?:" + "|".join(re.escape(c) for c in _CHAIN_LANDMARKS + _ADMIN_DISTRICTS) + r")"
    r"[\u4e00-\u9fff]{0,8}(?:附近|旁邊|對面|隔壁|那邊|這邊|一帶)"
)


# ══════════════════════════════════════════════════════════════
# 3 個自訂邏輯 recognizer
# ══════════════════════════════════════════════════════════════

class AmountTxnPure(Recognizer):
    """高風險交易動詞觸發金額，不依賴鄰近帳號。"""
    name = "AmountTxnPure"

    def __init__(self):
        verbs = "|".join(re.escape(v) for v in _HIGH_RISK_VERBS)
        self._re = re.compile(
            rf"(?:{verbs}).{{0,20}}?(\d+(?:,\d{{3}})*(?:元|塊|NTD|NT)?)"
            rf"|(\d+(?:,\d{{3}})*(?:元|塊|NTD|NT)?).{{0,10}}?(?:{verbs})"
        )

    def analyze(self, text: str) -> List[Span]:
        results: List[Span] = []
        for m in self._re.finditer(text):
            num = m.group(1) or m.group(2)
            if not num:
                continue
            idx = text.find(num, m.start())
            if idx == -1:
                continue
            results.append(Span(
                "AMOUNT_TXN", idx, idx + len(num), 0.82,
                Explanation(self.name, "AMOUNT_TXN_VERB",
                            score_context_improvement=0.35,
                            supportive_context_word="(verb)"),
            ))
        return results


class AddressEnhancedPure(Recognizer):
    """地址三層偵測：行政區+路 / 連鎖地標 / 地標後綴+近鄰表達。"""
    name = "AddressEnhancedPure"

    def __init__(self):
        districts = "|".join(re.escape(d) for d in _ADMIN_DISTRICTS)
        chains = "|".join(re.escape(c) for c in _CHAIN_LANDMARKS)
        self._L1 = re.compile(
            rf"(?:{districts})"
            r"[\u4e00-\u9fff]{0,15}?"
            r"(?:路|街|大道)"
            r"(?:[\u4e00-\u9fff]?段)?"
            r"(?:\d{1,4}巷)?"
            r"(?:\d{1,4}弄)?"
            r"(?:\d{1,4}號)?"
            r"(?:\d{1,3}樓)?"
            r"(?:之\d{1,3})?"
        )
        self._L2 = re.compile(rf"(?:{chains}).{{0,4}}(?:店|門市|分店|賣場)?")
        self._L3_LM = re.compile(_LANDMARK_SUFFIX)
        self._L3_PX = re.compile(_PROXIMITY)

    def analyze(self, text: str) -> List[Span]:
        results: List[Span] = []

        def _add(m: re.Match, score: float, layer: str) -> None:
            results.append(Span(
                "LOCATION", m.start(), m.end(), score,
                Explanation(self.name, layer),
            ))

        for m in self._L1.finditer(text):    _add(m, 0.85, "ADDR_L1_ADMIN")
        for m in self._L2.finditer(text):    _add(m, 0.75, "ADDR_L2_CHAIN")
        for m in self._L3_LM.finditer(text): _add(m, 0.70, "ADDR_L3_LANDMARK")
        for m in self._L3_PX.finditer(text): _add(m, 0.72, "ADDR_L3_PROXIMITY")
        return results


class VerificationAnswerPure(Recognizer):
    """驗證問題答案：trigger 關鍵字後 30 字內的 6-8 位數字。"""
    name = "VerificationAnswerPure"

    def __init__(self):
        triggers = "|".join(re.escape(k) for k in _VERIFICATION)
        self._trigger = re.compile(triggers)
        self._answer = re.compile(r"\d{6,8}")
        self._window = 30

    def analyze(self, text: str) -> List[Span]:
        results: List[Span] = []
        for tm in self._trigger.finditer(text):
            ws = tm.end()
            we = min(len(text), ws + self._window)
            for am in self._answer.finditer(text[ws:we]):
                results.append(Span(
                    "VERIFICATION_ANSWER",
                    ws + am.start(), ws + am.end(), 0.75,
                    Explanation(self.name, "VERIFICATION_TRIGGER",
                                score_context_improvement=0.35,
                                supportive_context_word=tm.group(0)),
                ))
        return results


# ══════════════════════════════════════════════════════════════
# Factory
# ══════════════════════════════════════════════════════════════

def get_pure_recognizers() -> List[Recognizer]:
    """回傳 21 個純 regex recognizer（18 pattern + 3 自訂），不含 CKIP。"""
    return [
        PurePatternRecognizer("TW_PHONE", [
            ("MOBILE",   r"09\d{8}",       0.85),
            ("LANDLINE", r"0[2-8]\d{7,8}", 0.75),
        ], _PHONE_CONTEXT),
        PurePatternRecognizer("TW_ID_NUMBER", [
            ("TW_ID", r"[A-Za-z][12]\d{8}", 0.90),
        ], _ID_CONTEXT),
        PurePatternRecognizer("PASSPORT", [
            ("PASSPORT", r"[A-Z]{1,2}\d{7,9}", 0.70),
        ], _PASSPORT_CONTEXT),
        PurePatternRecognizer("DOB", [
            ("DOB_8",     r"\d{8}", 0.50),
            ("DOB_SLASH", r"\d{4}[/-]\d{2}[/-]\d{2}", 0.70),
        ], _DOB_CONTEXT),
        PurePatternRecognizer("TW_CREDIT_CARD", [
            ("CC_16", r"\d{16}", 0.55),
        ], _CC_CONTEXT),
        PurePatternRecognizer("TW_BANK_ACCOUNT", [
            ("BANK_ACCT", r"(?!09\d{8})\d{10,14}", 0.50),
        ], _BANK_CONTEXT),
        PurePatternRecognizer("ATM_REF", [
            ("ATM_REF", r"\d{8,20}", 0.40),
        ], _ATM_CONTEXT),
        PurePatternRecognizer("LOAN_REF", [
            ("LOAN_REF_NUM",   r"\d{8,15}", 0.45),
            ("LOAN_REF_ALPHA", r"[A-Z]{1,3}\d{6,12}", 0.65),
        ], _LOAN_CONTEXT),
        PurePatternRecognizer("TXN_REF", [
            ("TXN_NUM",   r"\d{8,20}", 0.40),
            ("TXN_ALPHA", r"[A-Z]{1,3}\d{8,15}", 0.60),
        ], _TXN_CONTEXT),
        PurePatternRecognizer("POLICY_NO", [
            ("POLICY_ALPHA", r"[A-Z]\d{6,12}", 0.60),
            ("POLICY_NUM",   r"P\d{6,10}", 0.75),
        ], _POLICY_CONTEXT),
        PurePatternRecognizer("AMOUNT", [
            ("AMOUNT_YUAN", r"\d+(?:,\d{3})*元", 0.80),
            ("AMOUNT_KUAI", r"\d+(?:,\d{3})*塊", 0.75),
            ("AMOUNT_NT",   r"NT\$?\s*\d+(?:,\d{3})*", 0.80),
            ("AMOUNT_NUM",  r"\d+(?:,\d{3})*", 0.40),
        ], _AMOUNT_CONTEXT),
        AmountTxnPure(),
        PurePatternRecognizer("OTP", [
            ("OTP_6", r"\d{6}", 0.5),
        ], _OTP_CONTEXT),
        PurePatternRecognizer("CVV", [
            ("CVV_3", r"\d{3}", 0.30),
        ], _CVV_CONTEXT),
        PurePatternRecognizer("EXPIRY", [
            ("EXPIRY_MMYY",  r"(?:0[1-9]|1[0-2])\d{2}", 0.45),
            ("EXPIRY_SLASH", r"(?:0[1-9]|1[0-2])/\d{2}", 0.65),
        ], _EXPIRY_CONTEXT),
        PurePatternRecognizer("PIN", [
            ("PIN_46", r"\d{4,6}", 0.30),
        ], _PIN_CONTEXT),
        AddressEnhancedPure(),
        PurePatternRecognizer("STAFF_ID", [
            ("STAFF_ALPHA",  r"[A-Z]\d{4,8}", 0.55),
            ("STAFF_PREFIX", r"(?:EMP|STAFF|E|A)\d{4,8}", 0.70),
        ], _STAFF_CONTEXT),
        PurePatternRecognizer("CAMPAIGN", [
            ("CAMPAIGN_CODE", r"[A-Z]{2,4}\d{3,6}", 0.50),
        ], _CAMPAIGN_CONTEXT),
        PurePatternRecognizer("BRANCH", [
            ("BRANCH_NUM",   r"\d{3,4}", 0.35),
            ("BRANCH_ALPHA", r"[A-Z]{2,4}\d{2,4}", 0.55),
        ], _BRANCH_CONTEXT),
        VerificationAnswerPure(),
        # Email — 補 Presidio predefined EmailRecognizer 的缺口
        PurePatternRecognizer("EMAIL_ADDRESS", [
            ("EMAIL", r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", 0.85),
        ], _EMAIL_CONTEXT),
    ]

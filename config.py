# masking/config.py  v3
"""
脫敏規則表 v3 — 設定檔
v3 新增：Priority Engine、Conflict Resolution、AMOUNT_TXN、
         地址地標詞庫、語料可用度標記、Diarization 強化 fallback
"""

# ══════════════════════════════════════════════════════════════
# 實體類型 → 脫敏 Token
# ══════════════════════════════════════════════════════════════
TOKEN_MAP: dict[str, str] = {
    "PERSON":               "[NAME]",
    "TW_PHONE":             "[PHONE]",        # Log 中記錄子類型 MOBILE/LANDLINE
    "TW_ID_NUMBER":         "[ID]",
    "PASSPORT":             "[PASSPORT]",
    "EMAIL_ADDRESS":        "[EMAIL]",
    "LOCATION":             "[ADDRESS]",
    "DOB":                  "[DOB]",
    "VERIFICATION_ANSWER":  "[VERIFICATION_ANSWER]",
    "TW_CREDIT_CARD":       "[CARD]",
    "TW_BANK_ACCOUNT":      "[ACCOUNT]",
    "ATM_REF":              "[ATM_REF]",
    "TXN_REF":              "[TXN_REF]",
    "LOAN_REF":             "[LOAN_REF]",
    "POLICY_NO":            "[POLICY_NO]",
    "AMOUNT":               "[AMOUNT]",       # 條件式：與帳號/卡號並存
    "AMOUNT_TXN":           "[AMOUNT_TXN]",   # ★v3：高風險交易動詞觸發
    "OTP":                  "[OTP]",
    "EXPIRY":               "[EXPIRY]",
    "CVV":                  "[CVV]",
    "PIN":                  "[PIN]",
    "STAFF_ID":             "[STAFF_ID]",
    "CAMPAIGN":             "[CAMPAIGN]",
    "BRANCH":               "[BRANCH]",
}

# ══════════════════════════════════════════════════════════════
# ★v3 Priority Engine — 數字類實體優先級
# 數值越高優先級越高，同一 span 只保留最高優先級者
# 公式：final_score = base_priority×0.4 + type_score×0.4 + keyword_bonus×0.2
# ══════════════════════════════════════════════════════════════
ENTITY_PRIORITY: dict[str, int] = {
    "TW_CREDIT_CARD":   100,   # 16碼，最長最具體
    "TW_BANK_ACCOUNT":   90,   # 10-14碼 + keyword
    "TW_ID_NUMBER":      85,   # 含英文字母，識別性最高
    "DOB":               80,   # 固定 8 碼
    "OTP":               75,   # 6碼 + keyword
    "EXPIRY":            70,   # 4碼 MMYY + keyword
    "PIN":               65,   # 4-6碼 + keyword
    "CVV":               60,   # 3碼 + keyword（強制keyword觸發）
    "AMOUNT_TXN":        55,   # 高風險交易金額
    "AMOUNT":            50,   # 條件式金額（最後判斷）
    # 非數字類（不參與數字優先級競爭，但需加入以防混合 span 衝突）
    "PERSON":            95,
    "TW_PHONE":          88,
    "PASSPORT":          83,
    "EMAIL_ADDRESS":     82,
    "LOCATION":          78,
    "LOAN_REF":          72,
    "TXN_REF":           68,
    "ATM_REF":           66,
    "POLICY_NO":         64,
    "STAFF_ID":          62,
    "VERIFICATION_ANSWER": 58,
    "CAMPAIGN":          30,
    "BRANCH":            25,
}

# ★v3 風險等級（用於 Conflict Resolution Matrix）
# 數值越高風險越高
ENTITY_RISK_LEVEL: dict[str, int] = {
    "TW_CREDIT_CARD":    5,
    "TW_BANK_ACCOUNT":   5,
    "TW_ID_NUMBER":      5,
    "OTP":               5,
    "CVV":               5,
    "PIN":               5,
    "PERSON":            4,
    "TW_PHONE":          4,
    "PASSPORT":          4,
    "EMAIL_ADDRESS":     4,
    "DOB":               4,
    "VERIFICATION_ANSWER": 4,
    "AMOUNT_TXN":        3,
    "AMOUNT":            3,
    "LOCATION":          3,
    "LOAN_REF":          3,
    "TXN_REF":           2,
    "ATM_REF":           2,
    "POLICY_NO":         2,
    "EXPIRY":            4,
    "STAFF_ID":          2,
    "CAMPAIGN":          1,
    "BRANCH":            1,
}

# ══════════════════════════════════════════════════════════════
# 假名一致性實體
# ══════════════════════════════════════════════════════════════
PSEUDONYM_ENTITIES: set[str] = {
    "PERSON",
    "TW_CREDIT_CARD",
    "TW_BANK_ACCOUNT",
    "TXN_REF",
    "ATM_REF",
    "LOAN_REF",
}

# ══════════════════════════════════════════════════════════════
# 條件式脫敏設定
# ══════════════════════════════════════════════════════════════
AMOUNT_TRIGGER_ENTITIES: set[str] = {"TW_BANK_ACCOUNT", "TW_CREDIT_CARD"}
AMOUNT_PROXIMITY_CHARS: int = 60

# ★v3 高風險交易動詞（觸發 AMOUNT_TXN）
HIGH_RISK_TXN_VERBS: list[str] = [
    "轉帳", "匯款", "扣款", "刷卡", "付款", "繳費",
    "提款", "存款", "匯入", "撥款", "退款", "退費",
    "交易", "扣繳", "扣除", "入帳", "出帳",
]

# ══════════════════════════════════════════════════════════════
# 關鍵字 Context（Presidio 信心分數提升）
# ══════════════════════════════════════════════════════════════
PHONE_CONTEXT      = ["電話", "手機", "市話", "聯絡", "號碼", "撥打", "回撥", "致電", "phone", "mobile"]
ID_CONTEXT         = ["身分證", "身份證", "證號", "ID", "字號"]
CREDIT_CARD_CONTEXT= ["卡號", "信用卡", "卡", "刷卡", "card", "credit"]
BANK_ACCOUNT_CONTEXT=["帳號", "帳戶", "轉帳", "匯款", "存款", "account", "acct"]
OTP_CONTEXT        = ["驗證碼", "一次性密碼", "OTP", "簡訊碼", "認證碼", "動態密碼"]
CVV_CONTEXT        = ["背面三碼", "安全碼", "CVV", "CVC", "末三碼"]
EXPIRY_CONTEXT     = ["有效期限", "到期", "效期", "expiry", "expiration", "valid"]
PIN_CONTEXT        = ["密碼", "PIN", "網銀密碼", "提款密碼", "交易密碼"]
DOB_CONTEXT        = ["生日", "出生", "生年月日", "birthday", "birth", "出生日期"]
AMOUNT_CONTEXT     = ["元", "塊", "錢", "金額", "餘額", "NT", "NTD"] + HIGH_RISK_TXN_VERBS
STAFF_ID_CONTEXT   = ["工號", "員工編號", "行員", "客服代號", "staff", "employee"]
PASSPORT_CONTEXT   = ["護照", "passport"]
LOAN_CONTEXT       = ["貸款", "合約號", "借款", "loan", "合約"]
TXN_CONTEXT        = ["交易", "流水號", "序號", "transaction", "txn", "ref"]
ATM_CONTEXT        = ["ATM", "交易序號", "自動提款", "參考號碼"]
CAMPAIGN_CONTEXT   = ["活動", "專案", "行銷", "campaign", "promo"]
VERIFICATION_CONTEXT=["母親", "媽媽", "驗證問題", "安全問題", "母親姓名", "母親生日"]
POLICY_CONTEXT     = ["保單", "保險單", "policy", "投保"]
BRANCH_CONTEXT     = ["分行", "分行代碼", "branch", "分店"]

# ══════════════════════════════════════════════════════════════
# ★v3 地址強化三層設定
# ══════════════════════════════════════════════════════════════

# 第一層：行政區字典
ADMIN_DISTRICTS: list[str] = [
    "台北市", "臺北市", "新北市", "桃園市", "台中市", "臺中市",
    "台南市", "臺南市", "高雄市", "基隆市", "新竹市", "嘉義市",
    "新竹縣", "苗栗縣", "彰化縣", "南投縣", "雲林縣", "嘉義縣",
    "屏東縣", "宜蘭縣", "花蓮縣", "台東縣", "臺東縣",
    "澎湖縣", "金門縣", "連江縣",
    # 區/鄉/鎮（高頻）
    "中和", "板橋", "新店", "永和", "三重", "蘆洲", "汐止",
    "土城", "樹林", "鶯歌", "三峽", "淡水", "林口", "泰山",
    "五股", "新莊", "中壢", "平鎮", "八德", "楊梅", "大溪",
    "左營", "鳳山", "三民", "苓雅", "前鎮", "小港",
    "北屯", "西屯", "南屯", "太平", "大里", "霧峰",
]

# 第二層：連鎖商業地標
CHAIN_LANDMARKS: list[str] = [
    "Costco", "costco", "好市多",
    "SOGO", "sogo", "太平洋",
    "家樂福", "大潤發", "全聯", "頂好", "愛買",
    "IKEA", "ikea",
    "麥當勞", "肯德基", "摩斯漢堡",
    "星巴克", "路易莎",
    "新光三越", "微風", "遠東百貨", "漢神", "統一阪急",
    "台鐵", "高鐵", "捷運",
]

# 第三層：在地地標 pattern（比詞庫更有彈性）
LANDMARK_SUFFIX_PATTERN: str = (
    r"[\u4e00-\u9fff]{2,6}"
    r"(?:國小|國中|高中|大學|國小|醫院|診所|公園|廟|宮|"
    r"捷運站|火車站|高鐵站|客運站|機場|"
    r"夜市|市場|商圈|購物中心|廣場)"
)

# 近鄰表達 pattern（「X附近」「X旁邊」）
PROXIMITY_PATTERN: str = (
    r"(?:"
    + "|".join(CHAIN_LANDMARKS + ADMIN_DISTRICTS)
    + r")"
    r"[\u4e00-\u9fff]{0,8}(?:附近|旁邊|對面|隔壁|那邊|這邊|一帶)"
)

# ══════════════════════════════════════════════════════════════
# ★v3 Diarization Fallback 強化
# ══════════════════════════════════════════════════════════════
SPEAKER_AGENT: str    = "AGENT"
SPEAKER_CUSTOMER: str = "CUSTOMER"
FALLBACK_ANSWER_WINDOW_CHARS: int = 30

# 問句觸發 pattern（客服端）
AGENT_QUESTION_PATTERNS: list[str] = [
    r"請問您的.{0,15}[是為]",
    r"請問您.{0,10}[嗎？?]",
    r"可以.{0,8}嗎",
    r"需要.{0,6}驗證",
    r"確認一下您的",
    r"報一下您的",
    r"幫我.{0,6}確認",
]

# ★v3 回答模式（客戶端）—— 接在問句後 N 字內
ANSWER_PATTERNS: list[str] = [
    r"是\s*\d{4,16}",            # 「是123456」
    r"我的.{0,6}是\s*\d",        # 「我的電話是09...」
    r"對[，。,.]?\s*\d",          # 「對，123456」
    r"^\d{4,16}$",               # 純數字段（獨立回答）
    r"[\u4e00-\u9fff]{2,4}(?=[，。,.\s]|$)",  # 短中文（可能是姓名）
]

# ══════════════════════════════════════════════════════════════
# ★v3 語料可用度標記
# ══════════════════════════════════════════════════════════════
class UsabilityTag:
    USABLE            = "USABLE"
    DEGRADED_MASKING  = "DEGRADED_MASKING"    # 重度脫敏 > 3 entity/百字
    NO_DIARIZATION    = "NO_DIARIZATION"       # 無 speaker 標記
    FALLBACK_MODE     = "FALLBACK_MODE"        # Diarization 降級偵測
    LOW_AUDIO_QUALITY = "LOW_AUDIO_QUALITY"    # ASR 信心分低（外部傳入）

DEGRADED_MASKING_THRESHOLD: float = 3.0       # entity 數 / 百字

# ══════════════════════════════════════════════════════════════
# Audit Log 欄位
# ══════════════════════════════════════════════════════════════
AUDIT_FIELDNAMES: list[str] = [
    "session_id", "step", "rule_triggered", "entity_type",
    "entity_subtype",           # ★v3：MOBILE/LANDLINE/AMOUNT_TXN 等子類型
    "original_type_desc", "start", "end", "score",
    "token_applied", "conflict_resolved",  # ★v3：是否經過衝突解決
    "diarization_available", "usability_tag",  # ★v3
    "timestamp",
]

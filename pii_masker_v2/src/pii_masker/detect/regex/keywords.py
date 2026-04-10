"""Context keyword lists — ported from v3/v4 config.py.

These are kept in Python code (not YAML) because they're mostly stable and
easy to review here. If a deployment needs to override them per-environment,
the detector factory functions can accept overrides.
"""
from __future__ import annotations

PHONE: tuple[str, ...] = (
    "電話", "手機", "市話", "聯絡", "號碼", "撥打", "回撥", "致電",
    "phone", "mobile",
)
ID_NUMBER: tuple[str, ...] = (
    "身分證", "身份證", "證號", "ID", "字號",
)
CREDIT_CARD: tuple[str, ...] = (
    "卡號", "信用卡", "卡", "刷卡", "card", "credit",
)
BANK_ACCOUNT: tuple[str, ...] = (
    "帳號", "帳戶", "轉帳", "匯款", "存款", "account", "acct",
)
OTP: tuple[str, ...] = (
    "驗證碼", "一次性密碼", "OTP", "簡訊碼", "認證碼", "動態密碼",
)
CVV: tuple[str, ...] = (
    "背面三碼", "安全碼", "CVV", "CVC", "末三碼",
)
EXPIRY: tuple[str, ...] = (
    "有效期限", "到期", "效期", "expiry", "expiration", "valid",
)
PIN: tuple[str, ...] = (
    "密碼", "PIN", "網銀密碼", "提款密碼", "交易密碼",
)
DOB: tuple[str, ...] = (
    "生日", "出生", "生年月日", "birthday", "birth", "出生日期",
)
STAFF_ID: tuple[str, ...] = (
    "工號", "員工編號", "行員", "客服代號", "staff", "employee",
)
PASSPORT: tuple[str, ...] = (
    "護照", "passport",
)
LOAN: tuple[str, ...] = (
    "貸款", "合約號", "借款", "loan", "合約",
)
TXN: tuple[str, ...] = (
    "交易", "流水號", "序號", "transaction", "txn", "ref",
)
ATM: tuple[str, ...] = (
    "ATM", "交易序號", "自動提款", "參考號碼",
)
CAMPAIGN: tuple[str, ...] = (
    "活動", "專案", "行銷", "campaign", "promo",
)
VERIFICATION: tuple[str, ...] = (
    "母親", "媽媽", "驗證問題", "安全問題", "母親姓名", "母親生日",
)
POLICY: tuple[str, ...] = (
    "保單", "保險單", "policy", "投保",
)
BRANCH: tuple[str, ...] = (
    "分行", "分行代碼", "branch", "分店",
)
AMOUNT_BASE: tuple[str, ...] = (
    "元", "塊", "錢", "金額", "餘額", "NT", "NTD",
)

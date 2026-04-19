# masking/audit.py  v3
import csv
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional
from presidio_analyzer import RecognizerResult
from .config import AUDIT_FIELDNAMES

class AuditLogger:
    def __init__(self, log_path: str, append: bool = False):
        self._log_path = Path(log_path)
        self._log_path.parent.mkdir(parents=True, exist_ok=True)
        mode = "a" if append and self._log_path.exists() else "w"
        self._file   = open(self._log_path, mode, newline="", encoding="utf-8-sig")
        self._writer = csv.DictWriter(self._file, fieldnames=AUDIT_FIELDNAMES)
        if mode == "w":
            self._writer.writeheader()

    def log_v3(
        self,
        session_id:            str,
        step:                  str,
        result:                RecognizerResult,
        token_applied:         str,
        entity_subtype:        str  = "",
        conflict_resolved:     bool = False,
        diarization_available: bool = False,
        usability_tag:         str  = "USABLE",
    ):
        self._writer.writerow({
            "session_id":            session_id,
            "step":                  step,
            "rule_triggered":        self._recognizer_name(result),
            "entity_type":           result.entity_type,
            "entity_subtype":        entity_subtype,
            "original_type_desc":    self._type_desc(result.entity_type),
            "start":                 result.start,
            "end":                   result.end,
            "score":                 f"{result.score:.3f}",
            "token_applied":         token_applied,
            "conflict_resolved":     "Y" if conflict_resolved else "N",
            "diarization_available": "Y" if diarization_available else "N",
            "usability_tag":         usability_tag,
            "timestamp":             datetime.now(timezone.utc).isoformat(),
        })

    def flush(self): self._file.flush()
    def close(self): self._file.close()
    def __enter__(self): return self
    def __exit__(self, *a): self.close()

    _TYPE_DESC = {
        "PERSON":"姓名","TW_PHONE":"電話號碼","TW_ID_NUMBER":"身分證字號",
        "PASSPORT":"護照號碼","EMAIL_ADDRESS":"電子郵件","LOCATION":"地址/位置",
        "DOB":"出生日期","VERIFICATION_ANSWER":"驗證答案","TW_CREDIT_CARD":"信用卡號",
        "TW_BANK_ACCOUNT":"銀行帳號","ATM_REF":"ATM交易序號","TXN_REF":"交易流水號",
        "LOAN_REF":"貸款合約號","POLICY_NO":"保單號","AMOUNT":"交易金額（條件式）",
        "AMOUNT_TXN":"高風險交易金額","OTP":"OTP驗證碼","EXPIRY":"信用卡有效期限",
        "CVV":"CVV安全碼","PIN":"PIN密碼","STAFF_ID":"員工編號",
        "CAMPAIGN":"行銷專案代碼","BRANCH":"分行代碼",
    }

    @classmethod
    def _type_desc(cls, entity_type): return cls._TYPE_DESC.get(entity_type, entity_type)

    @staticmethod
    def _recognizer_name(result):
        if result.analysis_explanation:
            return result.analysis_explanation.recognizer or "unknown"
        return "unknown"

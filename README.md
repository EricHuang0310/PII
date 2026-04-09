# PII Masking Pipeline (v3)

台灣銀行語音 / STT 逐字稿 PII 遮罩 pipeline，建構於 Microsoft Presidio 之上，搭配中文 regex recognizer 與 CKIP Transformers NER，為電話客服對話中的敏感資訊提供一致且可稽核的遮罩。

- **輸入**：中文語音逐字稿（單句或 `DialogueTurn` 對話序列）
- **輸出**：遮罩後文字、實體清單、假名對照表、衝突解決記錄、可用度標記、CSV Audit Log
- **規範來源**：`003_脫敏規則表_v3.docx`，規則落地在 `config.py`

## 特色

- **20+ 個客製 recognizer**：電話、身分證、護照、信用卡、銀行帳號、ATM/TXN/LOAN/POLICY 序號、OTP/CVV/PIN、DOB、員工編號、保單號、行銷代碼、三層地址偵測等
- **雙重 NER**：Presidio 內建 spaCy NER + **必要** CKIP Transformers NER（中文 PERSON / LOCATION 偵測主力），由 ConflictResolver 自動去重
- **Conflict Resolver**：5 層決勝（Exact Dup → Contains → Risk Level → Span Length → Priority Score）
- **固定 token 遮罩**：同類型實體一律輸出 base token（例：所有 PERSON 都變 `[NAME]`、所有 TW_CREDIT_CARD 都變 `[CARD]`），不帶 `_1`/`_2` 編號
- **條件式金額**：`AMOUNT` 只在鄰近帳號/卡號時才遮罩；`AMOUNT_TXN` 由高風險交易動詞觸發即遮罩
- **Diarization 降級**：無 speaker 標記時以問答 pattern 提升信心分
- **可用度標記**：`USABLE` / `DEGRADED_MASKING` / `FALLBACK_MODE` / `NO_DIARIZATION` / `LOW_AUDIO_QUALITY`
- **Audit Log**：每個實體一筆 CSV row，包含 rule、entity type、score、conflict 結果、usability tag、timestamp

## 安裝

CKIP Transformers 為必要組件：

```bash
pip install presidio-analyzer presidio-anonymizer spacy
pip install ckip-transformers torch      # 必要：中文 PERSON/LOCATION NER
pip install openpyxl                     # 可選：Excel 批次
```

中文 spaCy 模型（可選，若省略則 spaCy 內建 NER 不觸發，但 regex recognizer 與 CKIP 仍正常運作）：

```bash
python -m spacy download zh_core_web_sm
```

> CKIP 模型首次執行時會自動下載並常駐記憶體（預設 `bert-base`，可改用 `albert-base` / `bert-tiny`）。

## 快速開始

### 單句遮罩

```python
from pipeline import MaskingPipeline

with MaskingPipeline(log_path="audit.csv") as p:
    r = p.mask(
        text="我叫王小明，卡號1234567890123456",
        session_id="S001",
        diarization_available=True,
    )
    print(r.masked_text)       # 我叫[NAME],卡號[CARD]
    print(r.entities_found)    # [PERSON, TW_CREDIT_CARD]
    print(r.usability_tag)     # USABLE / DEGRADED_MASKING / ...
```

### 對話批次遮罩

```python
from pipeline import MaskingPipeline, DialogueTurn

turns = [
    DialogueTurn(speaker="AGENT",    text="請問您的大名？"),
    DialogueTurn(speaker="CUSTOMER", text="我叫王小明"),
    DialogueTurn(speaker="CUSTOMER", text="我要轉帳50000元到12345678901234"),
]

with MaskingPipeline(log_path="audit.csv") as p:
    results = p.mask_dialogue(turns, session_id="S001")
    for r in results:
        print(r.masked_text)
```

> 所有 PERSON 都遮為 `[NAME]`、所有 `TW_BANK_ACCOUNT` 都遮為 `[ACCOUNT]`，
> 不會出現 `_1` / `_2` 編號。`MaskingResult.pseudonym_map` 仍會列出哪些
> 原始值被遮為同一 token，供 audit 檢視。

### 內建 demo

```bash
python pipeline.py        # 使用 spacy.blank("zh")，CKIP 負責 PERSON/LOCATION
```

> 首次執行時 CKIP 會下載並載入 NER 模型，需事先 `pip install ckip-transformers torch`。

## 架構：6 步驟 Pipeline

`MaskingPipeline.mask()`（`pipeline.py`）是單筆入口，`mask_dialogue()` 為對話 wrapper 並共用 `PseudonymTracker`：

| Step | 作用 | 關鍵模組 |
|---|---|---|
| 0 | 正規化（NFC、全形半形、中文數字、民國年、STT 語助詞、空白） | `normalizer.normalize` |
| 1+2 | Presidio 分析（regex + CKIP NER） | `recognizers.get_all_custom_recognizers` |
| 3 | 銀行規則（條件式 AMOUNT、speaker-aware boost） | `pipeline._apply_bank_rules` |
| 4 | 衝突解決 | `conflict_resolver.ConflictResolver` |
| 5 | Token 替換（per-span，統一 base token） | `pseudonym.PseudonymTracker` |
| 6 | Audit log + 可用度標記 | `audit.AuditLogger` |

> v4 已移除 LLM recognizer（原 Step 4）。在實際部署中，下游 LLM 會在本 pipeline **產出 masked_text 之後**才介入處理，不再作為 pipeline 內部的 recognizer。

### ConflictResolver 決勝順序

1. **Exact Duplicate Dedup** — 相同 `(start, end, entity_type)` 只保留 score 最高者（同分保留先出現者）。處理 CKIP × `AddressEnhancedRecognizer` 對 LOCATION 的純重複偵測。
2. **Contains** — 完全包含時長者勝
3. **Risk Level** — 部分重疊時以 `ENTITY_RISK_LEVEL` 高者勝
4. **Span Length** — 同風險等級時長者勝
5. **Priority Score** — 最終以 `ENTITY_PRIORITY × 0.4 + risk × 4 + score + keyword_bonus × 0.1` 決勝

## 支援的實體類型

全部定義於 `config.py` 的 `TOKEN_MAP`：

| 類別 | 實體 |
|---|---|
| 個人識別 | `PERSON`、`TW_ID_NUMBER`、`PASSPORT`、`DOB`、`TW_PHONE`、`EMAIL_ADDRESS`、`LOCATION`、`ORG` |
| 金融帳戶 | `TW_CREDIT_CARD`、`TW_BANK_ACCOUNT` |
| 交易序號 | `ATM_REF`、`TXN_REF`、`LOAN_REF`、`POLICY_NO` |
| 金額 | `AMOUNT`（條件式）、`AMOUNT_TXN`（高風險動詞） |
| 認證 | `OTP`、`CVV`、`EXPIRY`、`PIN`、`VERIFICATION_ANSWER` |
| 行內 | `STAFF_ID`、`CAMPAIGN`、`BRANCH` |

`PERSON`、`LOCATION`、`ORG` 由 CKIP Transformers NER 偵測，其餘由 regex recognizer 處理。

新增實體類型時需同步修改：
1. `config.py` — `TOKEN_MAP`、`ENTITY_PRIORITY`、`ENTITY_RISK_LEVEL`
2. `recognizers.py` — 新 recognizer class + 加入 `get_all_custom_recognizers`
3. `audit.py` — `_TYPE_DESC` 中文描述
4. （可選）`PSEUDONYM_ENTITIES` — 若需將該實體的原始值列入 `pseudonym_map` 供 audit 檢視

## MaskingResult 欄位

```python
@dataclass
class MaskingResult:
    session_id:            str
    original_text:         str
    normalized_text:       str
    masked_text:           str
    entities_found:        List[RecognizerResult]
    token_map:             Dict[int, str]             # id(result) → token
    pseudonym_map:         Dict[str, Dict[str, str]]  # entity_type → {original: token}
    conflict_log:          List[Tuple]                # (winner, loser, reason)
    diarization_available: bool
    usability_tag:         str
    fallback_mode:         bool
```

## 設定檔（`config.py`）

重要可調參數：

| 參數 | 預設 | 用途 |
|---|---|---|
| `AMOUNT_PROXIMITY_CHARS` | 60 | AMOUNT 視為「與帳號並存」的最大距離 |
| `HIGH_RISK_TXN_VERBS` | 轉帳、匯款… | 觸發 `AMOUNT_TXN` 的動詞白名單 |
| `FALLBACK_ANSWER_WINDOW_CHARS` | 30 | 無 diarization 時問句後的答題視窗 |
| `DEGRADED_MASKING_THRESHOLD` | 3.0 | 每百字遮罩超過此數即標 `DEGRADED_MASKING` |
| `ENTITY_PRIORITY` / `ENTITY_RISK_LEVEL` | 見檔 | 衝突解決用 |
| `ADMIN_DISTRICTS` / `CHAIN_LANDMARKS` | 見檔 | 地址三層偵測詞庫 |

## Audit Log 欄位

CSV header 由 `config.AUDIT_FIELDNAMES` 定義：

```
session_id, step, rule_triggered, entity_type, entity_subtype,
original_type_desc, start, end, score, token_applied,
conflict_resolved, diarization_available, usability_tag, timestamp
```

## 已知 v3 Bug 修正（勿回退）

觸碰以下區域時請保留既有修正，重新引入即為 regression：

- **`pipeline._apply_per_span_replacement`** — 不得改回 Presidio `anonymize()` 加 entity_type-keyed operators，否則同類型多筆會互蓋
- **`pipeline._compute_usability`** — `in_fallback` 參數冗餘已移除；直接以 `diarization_available` + 是否偵測到問句分支
- **`ConflictResolver.resolve` Step 0** — `(start, end, entity_type)` 完全相同時的 dedup，處理 CKIP × spaCy 重複偵測；`conflict_log` 存放 `RecognizerResult` 物件（非 entity_type 字串）以便 `pipeline.py` 以 `id(winner)` 追蹤 audit 的 `conflict_resolved` 欄位
- **`normalizer.normalize`** — 中文數字必須在民國年之前執行；`_parse_zh_number` 支援十/百/千位值；`_clean_stt_repeats` 只壓縮 `_STT_FILLER_CHARS` 中的語助詞
- **`mask_dialogue`** — `diarization_available` 以「labeled-speaker 覆蓋率 ≥ threshold」判斷，非 `any(...)`

## v4 變更

- **固定 token 遮罩**：`PseudonymTracker.resolve()` 一律回傳 `base_token`，不再累計 `_1`/`_2` 編號。`pseudonym_map` 仍保留原始值對應（同值只列一次），供 audit 使用。
- **CKIP 為必要組件**：移除 `MaskingPipeline.enable_ckip` 參數；`get_all_custom_recognizers` 永遠註冊 `CkipNerRecognizer`。若未安裝 `ckip-transformers`，首次 `mask()` 呼叫會拋出 `ImportError`。

## 檔案結構

```
PII/
├── pipeline.py              # MaskingPipeline 主入口 + demo()
├── recognizers.py           # 20+ custom Presidio recognizer
├── ckip_recognizer.py       # CKIP Transformers NER wrapper
├── conflict_resolver.py     # 衝突解決器（含 Exact Dup dedup）
├── pseudonym.py             # Session 層級假名追蹤
├── normalizer.py            # Step 0 文字正規化
├── audit.py                 # CSV Audit logger
├── config.py                # 全部設定 / 詞庫 / 優先級
├── CLAUDE.md                # 開發者協作指南
└── 003_脫敏規則表_v3.docx   # 業務規範原始檔
```

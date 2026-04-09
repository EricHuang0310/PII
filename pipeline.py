# masking/pipeline.py  v3  (bug-fixed)
"""
主脫敏管線 v3
新增：ConflictResolver、AMOUNT_TXN、語料可用度標記、Diarization 強化 fallback

修正紀錄（v3 bug-fix）：
  Bug 1 (嚴重) - operator_config 以 entity_type 為 key 導致同類型多筆互蓋
                 → 改為 per-span 的 OperatorConfig，以 Presidio ItemizedResult 處理
  Bug 2 (中等) - conflict_set 計算邏輯錯誤（把所有 result 都加入）且從未使用
                 → 改為正確計算「有被 resolve 的 result id 集合」
  Bug 3 (中等) - conflict_resolved 以 entity_type 模糊比對，應以 id(r) 精確比對
                 → 改為查 resolved_ids 集合
  Bug 4 (輕微) - NO_DIARIZATION 分支永遠無法到達（in_fallback 恆等於 not diarization_available）
                 → 移除冗餘的 in_fallback 參數，直接以 diarization_available 判斷
"""
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple

from presidio_analyzer import AnalyzerEngine, RecognizerRegistry, RecognizerResult
from presidio_analyzer.nlp_engine import NlpEngineProvider
from presidio_anonymizer import AnonymizerEngine
from presidio_anonymizer.entities import OperatorConfig

from audit import AuditLogger
from config import (
    TOKEN_MAP, PSEUDONYM_ENTITIES, AMOUNT_TRIGGER_ENTITIES,
    AMOUNT_PROXIMITY_CHARS, AGENT_QUESTION_PATTERNS, ANSWER_PATTERNS,
    FALLBACK_ANSWER_WINDOW_CHARS, SPEAKER_AGENT, SPEAKER_CUSTOMER,
    UsabilityTag, DEGRADED_MASKING_THRESHOLD,
)
from conflict_resolver import ConflictResolver
from normalizer import normalize
from pseudonym import PseudonymTracker
from recognizers import get_all_custom_recognizers


@dataclass
class MaskingResult:
    session_id:            str
    original_text:         str
    normalized_text:       str
    masked_text:           str
    entities_found:        List[RecognizerResult]    = field(default_factory=list)
    token_map:             Dict[int, str]            = field(default_factory=dict)
    pseudonym_map:         Dict[str, Dict[str, str]] = field(default_factory=dict)
    conflict_log:          List[Tuple]               = field(default_factory=list)
    diarization_available: bool = False
    usability_tag:         str  = UsabilityTag.USABLE
    fallback_mode:         bool = False

    @property
    def entity_count(self) -> int:
        return len(self.entities_found)

    @property
    def entity_types(self) -> List[str]:
        return list({r.entity_type for r in self.entities_found})


@dataclass
class DialogueTurn:
    speaker:        str
    text:           str
    start_time:     Optional[float] = None
    end_time:       Optional[float] = None
    asr_confidence: Optional[float] = None  # ★v3：ASR 信心分，供可用度標記使用


class MaskingPipeline:
    """
    銀行語音文字脫敏管線 v3
    Steps: 0 正規化 → 1+2 Presidio分析 → 3 銀行規則 → 4 LLM(可選)
           → 4.5 ★ConflictResolver → 5 假名一致性 → 6 Audit+可用度標記
    """
    _SUPPORTED_ENTITIES = list(TOKEN_MAP.keys())

    def __init__(
        self,
        log_path:                 Optional[str] = "audit_log.csv",
        score_threshold:          float = 0.60,
        mask_branch_code:         bool  = False,
        enable_llm_step:          bool  = False,
        enable_ckip:              bool  = False,
        ckip_model:               str   = "bert-base",
        ckip_device:              int   = -1,
        asr_confidence_threshold: float = 0.70,
        nlp_engine_name:          str   = "spacy",
        spacy_model:              str   = "zh_core_web_sm",
    ):
        self.score_threshold          = score_threshold
        self.mask_branch_code         = mask_branch_code
        self.enable_llm_step          = enable_llm_step
        self.enable_ckip              = enable_ckip
        self.ckip_model               = ckip_model
        self.ckip_device              = ckip_device
        self.asr_confidence_threshold = asr_confidence_threshold

        self._analyzer   = self._build_analyzer(nlp_engine_name, spacy_model)
        self._anonymizer = AnonymizerEngine()
        self._resolver   = ConflictResolver()

        self._llm_analyzer = None
        if enable_llm_step:
            self._llm_analyzer = self._build_llm_analyzer()

        self._logger: Optional[AuditLogger] = None
        if log_path:
            self._logger = AuditLogger(log_path)

        self._agent_q_pattern = re.compile("|".join(AGENT_QUESTION_PATTERNS))
        self._answer_patterns  = [re.compile(p) for p in ANSWER_PATTERNS]

    # ══════════════════════════════════════════════════════════
    # 公開方法
    # ══════════════════════════════════════════════════════════

    def mask(
        self,
        text:                  str,
        session_id:            str           = "",
        speaker:               Optional[str] = None,
        diarization_available: bool          = False,
        tracker:               Optional[PseudonymTracker] = None,
        asr_confidence:        Optional[float] = None,
    ) -> MaskingResult:
        if not text or not text.strip():
            return MaskingResult(
                session_id=session_id, original_text=text,
                normalized_text=text, masked_text=text,
            )

        # Step 0：正規化
        normalized = normalize(text)

        # Step 1+2：Presidio 分析
        entities_to_detect = list(self._SUPPORTED_ENTITIES)
        if not self.mask_branch_code and "BRANCH" in entities_to_detect:
            entities_to_detect.remove("BRANCH")

        raw_results = self._analyzer.analyze(
            text=normalized, entities=entities_to_detect,
            language="zh", score_threshold=self.score_threshold,
        )

        # Step 3：銀行特有規則（條件式金額、speaker-aware）
        results = self._apply_bank_rules(
            normalized, raw_results, speaker, diarization_available
        )

        # Step 4：LLM（可選）
        if self.enable_llm_step and self._llm_analyzer:
            results = self._merge_results(results, self._run_llm_step(normalized))

        # Step 4.5：Conflict Resolver
        results, conflict_log = self._resolver.resolve(results, normalized)

        # Step 5：假名一致性
        if tracker is None:
            tracker = PseudonymTracker(session_id=session_id)

        token_map: Dict[int, str] = {}
        for r in results:
            original_value = normalized[r.start:r.end]
            base_token     = TOKEN_MAP.get(r.entity_type, f"[{r.entity_type}]")
            token          = tracker.resolve(r.entity_type, original_value, base_token)
            token_map[id(r)] = token

        # ────────────────────────────────────────────────────
        # BUG 1 修正：改用 per-span OperatorConfig
        #
        # 原始問題：以 entity_type 為 key，同一類型多筆實體
        #           dict comprehension 後者蓋前者，只保留最後一個 token。
        #
        # 修正方案：Presidio anonymize() 接受 operators 字典以 entity_type 為 key，
        #           但其實無法做 per-span 的不同 token。
        #           解法：自行做字串替換（按 start 倒序，避免位移），
        #           繞過 anonymizer 的 entity_type-only 限制。
        # ────────────────────────────────────────────────────
        masked_text = self._apply_per_span_replacement(normalized, results, token_map)

        # Step 6：可用度標記
        # BUG 4 修正：移除恆等於 not diarization_available 的冗餘 in_fallback 參數
        usability_tag, fallback_mode = self._compute_usability(
            text=text,
            results=results,
            diarization_available=diarization_available,
            asr_confidence=asr_confidence,
        )

        # Step 6：Audit Log
        if self._logger:
            # BUG 2 修正：正確計算「有被 resolve 的 result id 集合」
            # conflict_log 的每筆 entry 格式為
            # (winner_result: RecognizerResult, loser_result: RecognizerResult, reason: str)
            # —— 詳見 ConflictResolver.resolve() 的回傳型別註解
            resolved_ids: Set[int] = set()
            for entry in conflict_log:
                if entry:
                    winner = entry[0]
                    if isinstance(winner, RecognizerResult):
                        resolved_ids.add(id(winner))

            for r in results:
                token   = token_map.get(id(r), r.entity_type)
                subtype = self._get_subtype(r)
                # BUG 3 修正：以 id(r) 精確比對，而非 entity_type 模糊比對
                conflict_resolved = id(r) in resolved_ids
                self._logger.log_v3(
                    session_id=session_id, step="Step1-5",
                    result=r, token_applied=token,
                    entity_subtype=subtype,
                    conflict_resolved=conflict_resolved,
                    diarization_available=diarization_available,
                    usability_tag=usability_tag,
                )

        return MaskingResult(
            session_id=session_id, original_text=text,
            normalized_text=normalized, masked_text=masked_text,
            entities_found=results, token_map=token_map,
            pseudonym_map=tracker.get_mapping(),
            conflict_log=conflict_log,
            diarization_available=diarization_available,
            usability_tag=usability_tag, fallback_mode=fallback_mode,
        )

    def mask_dialogue(
        self,
        turns:                 List[DialogueTurn],
        session_id:            str   = "",
        diarization_threshold: float = 0.8,
    ) -> List[MaskingResult]:
        tracker = PseudonymTracker(session_id=session_id)

        # Issue 3 修正：改以「有效標注覆蓋率」判斷，避免 partial diarization 誤判
        # 原本：any(t.speaker for t in turns) → 只要 1 筆有 speaker 就算有 diarization
        # 修正：有效標注的 turn 數 / 總 turn 數 >= threshold（預設 0.8）
        labeled_ratio = (
            sum(1 for t in turns if t.speaker in {SPEAKER_AGENT, SPEAKER_CUSTOMER})
            / max(len(turns), 1)
        )
        diarization_available = labeled_ratio >= diarization_threshold

        return [
            self.mask(
                text=t.text, session_id=session_id,
                speaker=t.speaker,
                diarization_available=diarization_available,
                tracker=tracker,
                asr_confidence=t.asr_confidence,
            )
            for t in turns
        ]

    def close(self):
        if self._logger:
            self._logger.close()

    def __enter__(self): return self
    def __exit__(self, *a): self.close()

    # ══════════════════════════════════════════════════════════
    # 私有方法
    # ══════════════════════════════════════════════════════════

    def _build_analyzer(self, nlp_engine_name: str, spacy_model: str) -> AnalyzerEngine:
        configuration = {
            "nlp_engine_name": nlp_engine_name,
            "models": [{"lang_code": "zh", "model_name": spacy_model}],
        }
        try:
            provider   = NlpEngineProvider(nlp_configuration=configuration)
            nlp_engine = provider.create_engine()
        except Exception as e:
            # Issue 8 修正：明確記錄降級警告，而非靜默 fallback
            import warnings
            warnings.warn(
                f"[MaskingPipeline] NLP engine 初始化失敗，"
                f"設定 engine={nlp_engine_name!r} model={spacy_model!r}，"
                f"原因：{e}。"
                f"將 fallback 至預設 engine，中文 NER 可能失效，請確認 spaCy 模型已安裝。",
                RuntimeWarning, stacklevel=2,
            )
            provider   = NlpEngineProvider()
            nlp_engine = provider.create_engine()

        registry = RecognizerRegistry(supported_languages=["zh", "en"])
        registry.load_predefined_recognizers(languages=["zh", "en"])
        for r in get_all_custom_recognizers(
            enable_ckip=self.enable_ckip,
            ckip_model=self.ckip_model,
            ckip_device=self.ckip_device,
        ):
            registry.add_recognizer(r)

        return AnalyzerEngine(
            registry=registry, nlp_engine=nlp_engine,
            supported_languages=["zh", "en"],
        )

    def _build_llm_analyzer(self):
        try:
            from presidio_analyzer.predefined_recognizers import AzureAILanguageRecognizer
            return AzureAILanguageRecognizer()
        except ImportError:
            print("[警告] Presidio LLM plugin 未安裝，Step 4 略過。")
            return None

    def _apply_bank_rules(
        self,
        text:                  str,
        results:               List[RecognizerResult],
        speaker:               Optional[str],
        diarization_available: bool,
    ) -> List[RecognizerResult]:
        results = self._apply_conditional_amount_masking(text, results)
        results = self._apply_speaker_aware_masking(text, results, speaker, diarization_available)
        return results

    def _apply_conditional_amount_masking(
        self,
        text:    str,
        results: List[RecognizerResult],
    ) -> List[RecognizerResult]:
        """
        AMOUNT：與帳號/卡號並存才脫敏（一般金額不脫敏）
        AMOUNT_TXN：高風險交易動詞觸發，直接脫敏（已由 recognizer 偵測）
        """
        amount_results  = [r for r in results if r.entity_type == "AMOUNT"]
        trigger_results = [r for r in results if r.entity_type in AMOUNT_TRIGGER_ENTITIES]

        if not trigger_results:
            # 無觸發實體 → 全部 AMOUNT 都不脫敏
            results = [r for r in results if r.entity_type != "AMOUNT"]
        else:
            keep_ids: Set[int] = set()
            for ar in amount_results:
                if any(
                    abs(ar.start - tr.start) <= AMOUNT_PROXIMITY_CHARS
                    for tr in trigger_results
                ):
                    keep_ids.add(id(ar))
            results = [r for r in results if r.entity_type != "AMOUNT" or id(r) in keep_ids]

        return results

    def _apply_speaker_aware_masking(
        self,
        text:                  str,
        results:               List[RecognizerResult],
        speaker:               Optional[str],
        diarization_available: bool,
    ) -> List[RecognizerResult]:
        """
        ★v3 強化：任何 speaker 只要包含敏感資料就脫敏。
        Diarization 的作用僅是輔助「問答配對」偵測，
        不是「只脫敏 CUSTOMER 發言」。

        `speaker` 參數目前未參與決策（設計刻意），保留在簽名中以便
        未來若銀行規範改為「僅客戶端遮罩」或「客服端放寬」時可就地切換，
        而不需要更動所有 call site。
        """
        if not diarization_available:
            # 降級策略：問句後 N 字元內的結果提升信心分
            for qm in self._agent_q_pattern.finditer(text):
                window_end = qm.end() + FALLBACK_ANSWER_WINDOW_CHARS
                for r in results:
                    if qm.end() <= r.start <= window_end:
                        r.score = min(1.0, r.score + 0.15)
            # 回答 pattern 輔助提升
            for ap in self._answer_patterns:
                for am in ap.finditer(text):
                    for r in results:
                        if am.start() <= r.start < am.end():
                            r.score = min(1.0, r.score + 0.10)
        return results

    @staticmethod
    def _apply_per_span_replacement(
        text:      str,
        results:   List[RecognizerResult],
        token_map: Dict[int, str],
    ) -> str:
        """
        BUG 1 修正：逐 span 替換，保留每個實體獨立的 token。

        按照 start 位置「由後往前」替換，避免替換後位移影響後續 span。
        """
        sorted_results = sorted(results, key=lambda r: r.start, reverse=True)
        for r in sorted_results:
            token = token_map.get(id(r), TOKEN_MAP.get(r.entity_type, f"[{r.entity_type}]"))
            text  = text[: r.start] + token + text[r.end :]
        return text

    def _compute_usability(
        self,
        text:                  str,
        results:               List[RecognizerResult],
        diarization_available: bool,
        asr_confidence:        Optional[float],
    ) -> Tuple[str, bool]:
        """
        ★v3：計算語料可用度標記。

        BUG 4 修正：移除恆為 not diarization_available 的 in_fallback 參數，
        並確保 NO_DIARIZATION / FALLBACK_MODE 邏輯正確分支。

        優先順序：
          1. 低音訊品質（ASR 信心分過低）
          2. 無 diarization：FALLBACK_MODE（有降級邏輯介入）
                           或 NO_DIARIZATION（純無 diarization，無降級介入）
          3. 有 diarization 但遮蔽密度過高：DEGRADED_MASKING
          4. 正常：USABLE
        """
        # 優先 1：音訊品質問題
        if asr_confidence is not None and asr_confidence < self.asr_confidence_threshold:
            return UsabilityTag.LOW_AUDIO_QUALITY, False

        # 優先 2：無 diarization
        if not diarization_available:
            # 有問句偵測降級邏輯介入 → FALLBACK_MODE
            # 無任何降級介入（連問句都沒有）→ NO_DIARIZATION
            has_fallback_signals = bool(self._agent_q_pattern.search(text))
            if has_fallback_signals:
                return UsabilityTag.FALLBACK_MODE, True
            return UsabilityTag.NO_DIARIZATION, False

        # 優先 3：遮蔽密度過高
        text_len = max(len(text), 1)
        density  = len(results) / text_len * 100
        if density > DEGRADED_MASKING_THRESHOLD:
            return UsabilityTag.DEGRADED_MASKING, False

        return UsabilityTag.USABLE, False

    def _merge_results(
        self,
        primary:   List[RecognizerResult],
        secondary: List[RecognizerResult],
    ) -> List[RecognizerResult]:
        """
        合併 primary (Presidio) 與 secondary (LLM) 結果。

        對相同 (start, end, entity_type) 的 span：保留 score 較高者；
        同分保留 primary（維持 Presidio 為主、LLM 為輔）。
        """
        by_key: Dict[Tuple[int, int, str], RecognizerResult] = {}
        order: List[Tuple[int, int, str]] = []
        for r in primary:
            key = (r.start, r.end, r.entity_type)
            if key not in by_key:
                order.append(key)
                by_key[key] = r
        for r in secondary:
            key = (r.start, r.end, r.entity_type)
            if key not in by_key:
                order.append(key)
                by_key[key] = r
            elif r.score > by_key[key].score:
                by_key[key] = r
        return [by_key[k] for k in order]

    def _run_llm_step(self, text: str) -> List[RecognizerResult]:
        try:
            return self._llm_analyzer.analyze(text=text, entities=["LOCATION", "PERSON"])
        except Exception as e:
            print(f"[警告] LLM Step 4 失敗：{e}")
            return []

    @staticmethod
    def _get_subtype(result: RecognizerResult) -> str:
        """取得子類型（MOBILE/LANDLINE/AMOUNT_TXN 等）。"""
        if result.analysis_explanation:
            pn = result.analysis_explanation.pattern_name or ""
            if pn in ("MOBILE", "LANDLINE"):
                return pn
            if pn == "AMOUNT_TXN_VERB":
                return "AMOUNT_TXN"
            if pn.startswith("ADDR_"):
                return pn
        return ""

def demo():
    """
    快速驗證完整 pipeline。
    使用 spaCy blank('zh') 作為 NLP engine，不需下載 zh_core_web_sm。
    Regex-based recognizer 全部正常運作，僅 spaCy NER (PERSON/LOCATION) 不會觸發。

    備註：要重現「CKIP × spaCy NER 在同 span 上重複偵測 PERSON/LOCATION」的場景，
    需改用：
        MaskingPipeline(enable_ckip=True, spacy_model="zh_core_web_sm")
    此時 Step 4.5 的 Exact Duplicate Dedup 會把相同 span+entity_type 的重複
    結果去重，並在 conflict_log 中記錄 reason="EXACT_DUP:...".
    """
    import spacy
    import tempfile, os
 
    # ── 建立 blank 中文模型到暫存目錄 ─────────────────────
    tmpdir = tempfile.mkdtemp()
    blank_path = os.path.join(tmpdir, "blank_zh")
    nlp = spacy.blank("zh")
    nlp.to_disk(blank_path)
    print(f"[INFO] 使用 spaCy blank('zh') 模型：{blank_path}")
 
    # ── 模擬對話 ──────────────────────────────────────────
    test_turns = [
        DialogueTurn(speaker="AGENT",    text="請問您的大名是？"),
        DialogueTurn(speaker="CUSTOMER", text="我叫王小明"),
        DialogueTurn(speaker="AGENT",    text="請問您的身分證字號？"),
        DialogueTurn(speaker="CUSTOMER", text="A一二三四五六七八九"),
        DialogueTurn(speaker="AGENT",    text="電話號碼幾號呢？"),
        DialogueTurn(speaker="CUSTOMER", text="零九一二三四五六七八"),
        DialogueTurn(speaker="AGENT",    text="信用卡卡號是多少？"),
        DialogueTurn(speaker="CUSTOMER", text="卡號1234567890123456"),
        DialogueTurn(speaker="AGENT",    text="請問驗證碼？"),
        DialogueTurn(speaker="CUSTOMER", text="驗證碼是654321"),
        DialogueTurn(speaker="AGENT",    text="需要轉帳多少？"),
        DialogueTurn(speaker="CUSTOMER", text="我要轉帳50000元到帳號12345678901234"),
        DialogueTurn(speaker="AGENT",    text="好的，請問您生日？"),
        DialogueTurn(speaker="CUSTOMER", text="生日是民國七十四年五月一日"),
        DialogueTurn(speaker="CUSTOMER", text="我住在台北市忠孝東路100號，Costco旁邊"),
        DialogueTurn(speaker="AGENT",    text="請問母親姓名是？"),
        DialogueTurn(speaker="CUSTOMER", text="母親姓名是陳美玲"),
    ]
 
    print("=" * 70)
    print("  PII 脫敏管線 v3 — Demo（blank 中文模型）")
    print("=" * 70)
 
    # ── 初始化 ────────────────────────────────────────────
    try:
        pipeline = MaskingPipeline(
            log_path="demo_audit_log.csv",
            score_threshold=0.50,
            spacy_model=blank_path,
        )
    except Exception as e:
        print(f"\n[錯誤] Pipeline 初始化失敗：{e}")
        print("請確認已安裝：pip install presidio-analyzer presidio-anonymizer spacy")
        return
 
    # ── 逐句處理 ──────────────────────────────────────────
    tracker = PseudonymTracker(session_id="demo_001")
 
    with pipeline:
        for i, turn in enumerate(test_turns, 1):
            result = pipeline.mask(
                text=turn.text,
                session_id="demo_001",
                speaker=turn.speaker,
                diarization_available=True,
                tracker=tracker,
            )
            print(f"\n[Turn {i:02d}] {turn.speaker}")
            print(f"  原始：{turn.text}")
            if result.normalized_text != turn.text:
                print(f"  正規：{result.normalized_text}")
            print(f"  脫敏：{result.masked_text}")
            if result.entities_found:
                ents = ", ".join(
                    f"{r.entity_type}({result.normalized_text[r.start:r.end]})"
                    for r in result.entities_found
                )
                print(f"  實體：{ents}")
            if result.conflict_log:
                for entry in result.conflict_log:
                    winner, loser, reason = entry
                    print(
                        f"  衝突：{winner.entity_type} 勝 {loser.entity_type} "
                        f"({reason})"
                    )
            print(f"  可用度：{result.usability_tag}")
 
    # ── 假名對照表 ────────────────────────────────────────
    print("\n" + "=" * 70)
    print("  假名對照表")
    print("=" * 70)
    mapping = tracker.get_mapping()
    if mapping:
        for entity_type, value_map in mapping.items():
            for original, token in value_map.items():
                print(f"  {entity_type}: {original} → {token}")
    else:
        print("  （無假名映射，blank 模型不會觸發 PERSON NER）")
 
    print(f"\n  Audit log → demo_audit_log.csv")
    print("=" * 70)
 
    # ── 清理暫存 ──────────────────────────────────────────
    import shutil
    shutil.rmtree(tmpdir, ignore_errors=True)
 
 
if __name__ == "__main__":
    demo()
"""
A 側 pipeline：Presidio + spaCy zh_core_web_sm + 20 custom regex（不含 CKIP）。

複用既有 recognizers.py 的 20 個 class（read-only import，不修改該檔），
但跳過 CkipNerRecognizer — 實現「純 spaCy NER」對照組。
"""
from __future__ import annotations

from typing import List, Tuple

from presidio_analyzer import AnalyzerEngine, RecognizerRegistry
from presidio_analyzer.nlp_engine import NlpEngineProvider

# 重用既有 recognizer class（不改原檔）
from recognizers import (
    TWPhoneRecognizer, TWIDRecognizer, PassportRecognizer, DOBRecognizer,
    TWCreditCardRecognizer, TWBankAccountRecognizer, ATMRefRecognizer,
    LoanRefRecognizer, TXNRefRecognizer, PolicyNoRecognizer,
    AmountRecognizer, AmountTxnRecognizer,
    OTPRecognizer, CVVRecognizer, ExpiryRecognizer, PINRecognizer,
    AddressEnhancedRecognizer,
    StaffIDRecognizer, CampaignRecognizer, BranchRecognizer,
    VerificationAnswerRecognizer,
)

from pipelines.b_pure.span import Span, Explanation
from conflict_resolver import ConflictResolver
from config import TOKEN_MAP as CONFIG_TOKEN_MAP


_SUPPORTED_ENTITIES: List[str] = list(CONFIG_TOKEN_MAP.keys())


def _build_20_recognizers():
    """實例化 20 個 custom recognizer（不含 Ckip）。"""
    return [
        TWPhoneRecognizer(), TWIDRecognizer(), PassportRecognizer(), DOBRecognizer(),
        TWCreditCardRecognizer(), TWBankAccountRecognizer(), ATMRefRecognizer(),
        LoanRefRecognizer(), TXNRefRecognizer(), PolicyNoRecognizer(),
        AmountRecognizer(), AmountTxnRecognizer(),
        OTPRecognizer(), CVVRecognizer(), ExpiryRecognizer(), PINRecognizer(),
        AddressEnhancedRecognizer(),
        StaffIDRecognizer(), CampaignRecognizer(), BranchRecognizer(),
        VerificationAnswerRecognizer(),
    ]


def _presidio_result_to_span(r) -> Span:
    """轉換 Presidio RecognizerResult → comparison.Span，讓 ConflictResolver 統一處理。"""
    exp_src = r.analysis_explanation
    if exp_src is None:
        exp = Explanation()
    else:
        exp = Explanation(
            recognizer=getattr(exp_src, "recognizer", "") or "",
            pattern_name=getattr(exp_src, "pattern_name", None),
            score_context_improvement=getattr(exp_src, "score_context_improvement", 0.0) or 0.0,
            supportive_context_word=getattr(exp_src, "supportive_context_word", None),
        )
    return Span(r.entity_type, r.start, r.end, r.score, exp)


class PipelineA:
    """Presidio AnalyzerEngine + spaCy zh_core_web_sm + 20 custom regex（無 CKIP）。"""

    def __init__(self, spacy_model: str = "zh_core_web_sm", score_threshold: float = 0.50):
        self._score_threshold = score_threshold

        provider = NlpEngineProvider(nlp_configuration={
            "nlp_engine_name": "spacy",
            "models": [{"lang_code": "zh", "model_name": spacy_model}],
        })
        nlp_engine = provider.create_engine()

        registry = RecognizerRegistry(supported_languages=["zh", "en"])
        registry.load_predefined_recognizers(languages=["zh", "en"])
        for r in _build_20_recognizers():
            registry.add_recognizer(r)

        self._analyzer = AnalyzerEngine(
            registry=registry, nlp_engine=nlp_engine,
            supported_languages=["zh", "en"],
        )
        self._resolver = ConflictResolver()

    def mask(self, text: str) -> Tuple[str, List[Span], list]:
        raw = self._analyzer.analyze(
            text=text, entities=_SUPPORTED_ENTITIES,
            language="zh", score_threshold=self._score_threshold,
        )
        spans = [_presidio_result_to_span(r) for r in raw]
        clean, log = self._resolver.resolve(spans, text)
        masked = text
        for r in sorted(clean, key=lambda s: s.start, reverse=True):
            token = CONFIG_TOKEN_MAP.get(r.entity_type, f"[{r.entity_type}]")
            masked = masked[:r.start] + token + masked[r.end:]
        return masked, clean, log

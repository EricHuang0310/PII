# ckip_recognizer.py
"""
CKIP Transformers NER → Presidio EntityRecognizer 整合模組

將 CkipNerChunker 包裝為 Presidio 的 EntityRecognizer，
專門偵測中文姓名（PERSON）與地點（LOCATION），
補足 regex recognizer 無法覆蓋的 NER 實體。

CKIP NER 標籤對照：
  PERSON       → PERSON（姓名）
  GPE          → LOCATION（地理政治實體，如國家、城市）
  LOC          → LOCATION（一般地點）
  ORG          → ORG（組織，目前不脫敏，保留供未來擴充）
  其他標籤      → 忽略

使用方式：
  from ckip_recognizer import CkipNerRecognizer

  # 初始化（只需一次，模型會常駐記憶體）
  recognizer = CkipNerRecognizer(
      model="bert-base",     # 或 "albert-base", "bert-tiny"
      device=0,              # GPU ID，-1 為 CPU
  )

  # 註冊到 Presidio
  registry.add_recognizer(recognizer)

安裝依賴：
  pip install ckip-transformers torch
"""

from __future__ import annotations

from typing import List, Optional, Set

from presidio_analyzer import EntityRecognizer, RecognizerResult, AnalysisExplanation
from presidio_analyzer.nlp_engine import NlpArtifacts


# CKIP NER 標籤 → Presidio entity_type 映射
_CKIP_TO_PRESIDIO = {
    "PERSON": "PERSON",
    "GPE":    "LOCATION",   # 地理政治實體（國家、縣市）
    "LOC":    "LOCATION",   # 一般地點
    "ORG":  "ORG",        # 未來可開啟
}


class CkipNerRecognizer(EntityRecognizer):
    """
    使用 CKIP Transformers 進行中文 NER 的 Presidio Recognizer。

    支援偵測：PERSON（中文姓名）、LOCATION（地點/地址）

    Parameters
    ----------
    model : str
        CKIP 預訓練模型名稱：
        - "bert-base"   : 精度最高，速度較慢（推薦）
        - "albert-base" : 精度略低，速度較快
        - "bert-tiny"   : 最快，精度最低（適合測試）
    device : int
        GPU device ID，-1 為 CPU
    score : float
        NER 結果的預設信心分數
    min_name_length : int
        PERSON 實體的最小字元長度（過濾單字誤判）
    """

    # 類別層級的模型快取，避免重複載入
    _shared_driver = None
    _shared_model_name = None

    def __init__(
        self,
        model: str = "bert-base",
        device: int = -1,
        score: float = 0.85,
        min_name_length: int = 2,
        supported_entities: Optional[List[str]] = None,
    ):
        self._model_name = model
        self._device = device
        self._default_score = score
        self._min_name_length = min_name_length

        entities = supported_entities or ["PERSON", "LOCATION"]

        super().__init__(
            supported_entities=entities,
            supported_language="zh",
            name="CkipNerRecognizer",
        )

    def load(self) -> None:
        """載入 CKIP NER 模型（延遲載入，首次 analyze 時觸發）。"""
        if (
            CkipNerRecognizer._shared_driver is not None
            and CkipNerRecognizer._shared_model_name == self._model_name
        ):
            self._driver = CkipNerRecognizer._shared_driver
            return

        try:
            from ckip_transformers.nlp import CkipNerChunker
        except ImportError:
            raise ImportError(
                "請安裝 ckip-transformers：pip install ckip-transformers torch"
            )

        print(f"[CkipNerRecognizer] 載入模型 {self._model_name!r} (device={self._device})...")
        self._driver = CkipNerChunker(model=self._model_name, device=self._device)

        # 快取到類別層級
        CkipNerRecognizer._shared_driver = self._driver
        CkipNerRecognizer._shared_model_name = self._model_name
        print(f"[CkipNerRecognizer] 模型載入完成")

    def analyze(
        self,
        text: str,
        entities: List[str],
        nlp_artifacts: Optional[NlpArtifacts] = None,
    ) -> List[RecognizerResult]:
        """
        對輸入文字執行 CKIP NER，回傳 Presidio RecognizerResult。
        """
        if not hasattr(self, "_driver") or self._driver is None:
            self.load()

        if not text or not text.strip():
            return []

        # CKIP 接受 List[str]，回傳 List[List[NerToken]]
        # NerToken = (word, ner, (start, end))
        try:
            ner_results = self._driver([text], use_delim=False, show_progress=False)
        except Exception as e:
            import warnings
            warnings.warn(f"[CkipNerRecognizer] NER 推論失敗：{e}", RuntimeWarning)
            return []

        results: List[RecognizerResult] = []

        if not ner_results or not ner_results[0]:
            return results

        for token in ner_results[0]:
            word = token.word
            ner_tag = token.ner
            start, end = token.idx

            # 映射 CKIP 標籤到 Presidio entity_type
            entity_type = _CKIP_TO_PRESIDIO.get(ner_tag)
            if entity_type is None:
                continue

            # 只處理請求的實體類型
            if entity_type not in entities:
                continue

            # PERSON 過濾：太短的可能是誤判
            if entity_type == "PERSON" and len(word) < self._min_name_length:
                continue

            # 建立 Presidio 結果
            explanation = AnalysisExplanation(
                recognizer=self.name,
                original_score=self._default_score,
                pattern_name=f"CKIP_{ner_tag}",
                pattern=word,
                validation_result=None,
            )

            results.append(RecognizerResult(
                entity_type=entity_type,
                start=start,
                end=end,
                score=self._default_score,
                analysis_explanation=explanation,
            ))

        return results


# ══════════════════════════════════════════════════════════════
# 快速測試
# ══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    recognizer = CkipNerRecognizer(model='bert-base', device=-1)
    recognizer.load()

    test_texts = [
        "我叫王小明，住在台北市",
        "請問黃鼎量先生的身分證字號",
        "陳美玲住在高雄市左營區博愛大道500號",
        "今天天氣不錯",
        "傅達仁今將執行安樂死",
    ]

    for text in test_texts:
        results = recognizer.analyze(text, ["PERSON", "LOCATION"])
        if results:
            ents = ", ".join(
                f"{r.entity_type}({text[r.start:r.end]})" for r in results
            )
            print(f"  {text} → {ents}")
        else:
            print(f"  {text} → (無)")
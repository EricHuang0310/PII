"""
CKIP Transformers NER wrapper — 純 Python，不繼承 Presidio。
產出 comparison.span.Span。
"""
from __future__ import annotations

from typing import List

from comparison.pure_recognizers import Recognizer
from comparison.span import Span, Explanation


class CKIPNer(Recognizer):
    name = "CKIP"
    _TAG_MAP = {"PERSON": "PERSON", "GPE": "LOCATION", "LOC": "LOCATION"}

    def __init__(self, model: str = "bert-base", device: int = -1):
        from ckip_transformers.nlp import CkipNerChunker
        self._driver = CkipNerChunker(model=model, device=device)

    def analyze(self, text: str) -> List[Span]:
        if not text.strip():
            return []
        ner = self._driver([text], use_delim=False, show_progress=False)
        if not ner or not ner[0]:
            return []
        out: List[Span] = []
        for tok in ner[0]:
            etype = self._TAG_MAP.get(tok.ner)
            if etype is None:
                continue
            out.append(Span(
                etype, tok.idx[0], tok.idx[1], 0.85,
                Explanation(self.name, f"CKIP_{tok.ner}"),
            ))
        return out

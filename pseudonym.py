# masking/pseudonym.py  v4
"""
Step 5：假名追蹤器

v4 變更（移除編號）：
  同類型實體統一使用 base_token，例如 PERSON 一律 → [NAME]，
  不再依出現順序加上 _1 / _2 / _3 的後綴。

  追蹤器仍保留 (entity_type → {original_value → token}) 的對照，
  供 MaskingResult.pseudonym_map 輸出與 audit 檢視「哪些原值被遮為同一 token」。
"""
from typing import Dict, Set

try:
    from config import PSEUDONYM_ENTITIES as _CFG_ENTITIES
    _DEFAULT_PSEUDONYM_ENTITIES: Set[str] = set(_CFG_ENTITIES)
except ImportError:
    _DEFAULT_PSEUDONYM_ENTITIES = {"PERSON", "ORG"}


class PseudonymTracker:
    """
    Session 層級的假名追蹤器（無編號版）。

        tracker.resolve("PERSON", "王小明", "[NAME]")  # → "[NAME]"
        tracker.resolve("PERSON", "陳美玲", "[NAME]")  # → "[NAME]"
    """

    def __init__(self, session_id: str = "", pseudonym_entities: Set[str] = None):
        self.session_id = session_id
        self._entities  = (
            set(pseudonym_entities)
            if pseudonym_entities is not None
            else _DEFAULT_PSEUDONYM_ENTITIES
        )
        self._value_to_token: Dict[str, Dict[str, str]] = {}

    def resolve(self, entity_type: str, original_value: str, base_token: str) -> str:
        if entity_type not in self._entities:
            return base_token

        if entity_type not in self._value_to_token:
            self._value_to_token[entity_type] = {}
        self._value_to_token[entity_type][original_value] = base_token
        return base_token

    def get_mapping(self) -> Dict[str, Dict[str, str]]:
        return {et: dict(vm) for et, vm in self._value_to_token.items()}

    def reset(self):
        self._value_to_token.clear()

    def __repr__(self) -> str:
        tracked = {et: len(vm) for et, vm in self._value_to_token.items()}
        return f"PseudonymTracker(session_id={self.session_id!r}, tracked={tracked})"

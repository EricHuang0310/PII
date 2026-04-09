# masking/pseudonym.py  v3.1  (Issue 5 implemented)
"""
Step 5：假名一致性追蹤器

Issue 5 修正：Token 命名從 _1 開始，與治理規範一致。
  第 1 個值 → [NAME_1]
  第 2 個值 → [NAME_2]
  第 3 個值 → [NAME_3]
"""
from typing import Dict, Set

try:
    from config import PSEUDONYM_ENTITIES as _CFG_ENTITIES
    _DEFAULT_PSEUDONYM_ENTITIES: Set[str] = set(_CFG_ENTITIES)
except ImportError:
    _DEFAULT_PSEUDONYM_ENTITIES = {"PERSON", "ORG"}


class PseudonymTracker:
    """
    Session 層級的假名一致性追蹤器。

        tracker.resolve("PERSON", "王小明", "[NAME]")  # → "[NAME_1]"
        tracker.resolve("PERSON", "王小明", "[NAME]")  # → "[NAME_1]"（一致）
        tracker.resolve("PERSON", "陳美玲", "[NAME]")  # → "[NAME_2]"
    """

    def __init__(self, session_id: str = "", pseudonym_entities: Set[str] = None):
        self.session_id = session_id
        self._entities  = (
            set(pseudonym_entities)
            if pseudonym_entities is not None
            else _DEFAULT_PSEUDONYM_ENTITIES
        )
        self._value_to_token: Dict[str, Dict[str, str]] = {}
        self._counter:        Dict[str, int]            = {}

    def resolve(self, entity_type: str, original_value: str, base_token: str) -> str:
        if entity_type not in self._entities:
            return base_token

        if entity_type not in self._value_to_token:
            self._value_to_token[entity_type] = {}
            self._counter[entity_type] = 0

        if original_value in self._value_to_token[entity_type]:
            return self._value_to_token[entity_type][original_value]

        self._counter[entity_type] += 1
        count = self._counter[entity_type]

        # Issue 5：從 _1 開始
        if base_token.endswith("]"):
            token = base_token[:-1] + f"_{count}]"
        else:
            token = f"{base_token}_{count}"

        self._value_to_token[entity_type][original_value] = token
        return token

    def get_mapping(self) -> Dict[str, Dict[str, str]]:
        return {et: dict(vm) for et, vm in self._value_to_token.items()}

    def reset(self):
        self._value_to_token.clear()
        self._counter.clear()

    def __repr__(self) -> str:
        return f"PseudonymTracker(session_id={self.session_id!r}, tracked={dict(self._counter)})"

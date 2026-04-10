"""PseudonymTracker — session-scoped, thread-safe token assignment.

Ports v3/v4 `PseudonymTracker` with two v2 changes:

1. **Thread safety**: internal `threading.Lock` guards the mapping. v3/v4
   assumed single-threaded access; v2 supports concurrent callers.
2. **Flat base tokens (v4 behavior)**: every PERSON becomes `[NAME]`, every
   credit card becomes `[CARD]`, etc. The mapping records the original
   values for audit but the token returned to the caller is always the
   base token.

The tracker is explicitly passed through `mask()` so there is no module-
global state. For dialogue mode, the caller creates one tracker and passes
it to every turn.
"""
from __future__ import annotations

import threading
from collections.abc import Mapping
from types import MappingProxyType

from pii_masker.domain.entity_type import EntityType


class PseudonymTracker:
    """Session-scoped mapping from (entity_type, original) → base token."""

    def __init__(self, session_id: str = "") -> None:
        self._session_id: str = session_id
        self._map: dict[EntityType, dict[str, str]] = {}
        self._lock: threading.Lock = threading.Lock()

    @property
    def session_id(self) -> str:
        return self._session_id

    def resolve(
        self,
        entity_type: EntityType,
        original: str,
        base_token: str,
    ) -> str:
        """Record the mapping and return the base token.

        Thread-safe. Returns the same base token for the same
        (entity_type, original) across calls — the map is for audit only,
        since the token is flat.
        """
        with self._lock:
            type_map = self._map.setdefault(entity_type, {})
            if original not in type_map:
                type_map[original] = base_token
            return type_map[original]

    def get_mapping(self) -> Mapping[EntityType, Mapping[str, str]]:
        """Return a read-only view of the full tracker state.

        The returned mapping is a frozen snapshot — mutations to the
        tracker after this call are not reflected. Use this to populate
        `MaskingResult.pseudonym_map`.
        """
        with self._lock:
            return MappingProxyType(
                {
                    k: MappingProxyType(dict(v))
                    for k, v in self._map.items()
                }
            )

"""JsonlAuditSink — writes one JSON line per AuditEvent.

This is the DEFAULT sink for v2. JSONL is grep-friendly, supports nested
fields if we ever add them, and is the canonical format for log pipelines
(Datadog, Loki, ELK, etc.).
"""
from __future__ import annotations

import json
from collections.abc import Iterable
from pathlib import Path
from typing import IO, Optional

from pii_masker.audit.event import AuditEvent
from pii_masker.audit.schema import event_as_dict


class JsonlAuditSink:
    def __init__(self, path: Path | str, *, append: bool = False) -> None:
        self._path: Path = Path(path)
        self._append: bool = append
        self._fp: Optional[IO[str]] = None

    def _open(self) -> None:
        if self._fp is not None:
            return
        mode = "a" if self._append else "w"
        self._fp = self._path.open(mode, encoding="utf-8")

    def write(self, event: AuditEvent) -> None:
        if self._fp is None:
            self._open()
        assert self._fp is not None
        row = event_as_dict(event)
        self._fp.write(json.dumps(row, ensure_ascii=False))
        self._fp.write("\n")
        self._fp.flush()

    def write_many(self, events: Iterable[AuditEvent]) -> None:
        for e in events:
            self.write(e)

    def close(self) -> None:
        if self._fp is not None:
            self._fp.close()
            self._fp = None

    def __enter__(self) -> "JsonlAuditSink":
        self._open()
        return self

    def __exit__(self, *a: object) -> None:
        self.close()

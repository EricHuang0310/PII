"""CsvAuditSink — writes one row per AuditEvent to a CSV file."""
from __future__ import annotations

import csv
from collections.abc import Iterable
from pathlib import Path
from typing import IO, Optional

from pii_masker.audit.event import AuditEvent
from pii_masker.audit.schema import AUDIT_FIELDNAMES, event_as_dict


class CsvAuditSink:
    """Append-only CSV sink.

    The schema is derived from AuditEvent at import time. Adding a field to
    AuditEvent automatically adds a column here — no manual sync.
    """

    def __init__(self, path: Path | str, *, append: bool = False) -> None:
        self._path: Path = Path(path)
        self._append: bool = append
        self._fp: Optional[IO[str]] = None
        self._writer: Optional[csv.DictWriter[str]] = None

    def _open(self) -> None:
        if self._fp is not None:
            return
        write_header = not (self._append and self._path.exists())
        mode = "a" if self._append else "w"
        self._fp = self._path.open(mode, encoding="utf-8", newline="")
        self._writer = csv.DictWriter(
            self._fp, fieldnames=list(AUDIT_FIELDNAMES)
        )
        if write_header:
            self._writer.writeheader()
            self._fp.flush()

    def write(self, event: AuditEvent) -> None:
        if self._writer is None:
            self._open()
        assert self._writer is not None
        assert self._fp is not None
        self._writer.writerow(event_as_dict(event))
        self._fp.flush()

    def write_many(self, events: Iterable[AuditEvent]) -> None:
        for e in events:
            self.write(e)

    def close(self) -> None:
        if self._fp is not None:
            self._fp.close()
            self._fp = None
            self._writer = None

    def __enter__(self) -> "CsvAuditSink":
        self._open()
        return self

    def __exit__(self, *a: object) -> None:
        self.close()

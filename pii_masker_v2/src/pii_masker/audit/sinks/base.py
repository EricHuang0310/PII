"""AuditSink Protocol — the port every audit backend implements."""
from __future__ import annotations

from collections.abc import Iterable
from typing import Protocol, runtime_checkable

from pii_masker.audit.event import AuditEvent


@runtime_checkable
class AuditSink(Protocol):
    """Writes AuditEvents to some backend (file, stdout, database, etc.)."""

    def write(self, event: AuditEvent) -> None:
        """Write a single event. Must be idempotent-safe under retry."""
        ...

    def write_many(self, events: Iterable[AuditEvent]) -> None:
        """Batch write. Default implementations should still be safe."""
        ...

    def close(self) -> None:
        """Flush and close any underlying handles."""
        ...

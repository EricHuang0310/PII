"""NullAuditSink — discards everything. Useful for tests and benchmarks."""
from __future__ import annotations

from collections.abc import Iterable

from pii_masker.audit.event import AuditEvent


class NullAuditSink:
    """An audit sink that discards every event. No-op everything."""

    def __init__(self) -> None:
        self._count: int = 0

    def write(self, event: AuditEvent) -> None:
        self._count += 1

    def write_many(self, events: Iterable[AuditEvent]) -> None:
        for _ in events:
            self._count += 1

    def close(self) -> None:
        pass

    @property
    def events_written(self) -> int:
        """Count of events received (useful for tests)."""
        return self._count

"""Span — a half-open text interval [start, end).

Frozen by design so that spans can be stored in sets, used as dict keys, and
compared for equality without worrying about hidden mutation.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Span:
    """Half-open character interval [start, end)."""

    start: int
    end: int

    def __post_init__(self) -> None:
        if self.start < 0:
            raise ValueError(f"Span.start must be >= 0, got {self.start}")
        if self.end < self.start:
            raise ValueError(
                f"Span.end ({self.end}) must be >= start ({self.start})"
            )

    @property
    def length(self) -> int:
        """Span length in characters."""
        return self.end - self.start

    def overlaps(self, other: Span) -> bool:
        """True if the two spans share at least one character.

        Touching spans (a.end == b.start) do NOT overlap.
        """
        return self.start < other.end and self.end > other.start

    def contains(self, other: Span) -> bool:
        """True if `other` is strictly contained in `self`.

        Strict means `self` must be STRICTLY longer than `other`. Equal-length
        spans do not count as containment — they go through the risk-level
        decision instead. This matches `conflict_resolver._contains` in v3/v4.
        """
        if self.length <= other.length:
            return False
        return self.start <= other.start and self.end >= other.end

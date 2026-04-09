"""Conflict resolver — composes dedup + overlap resolution layers.

Ports v3/v4 `ConflictResolver.resolve`. The composed flow:

    Step 0: dedup_exact       -- drop exact duplicates
    Step A: compute priority scores
    Step B: sort by (start, -length, -priority)
    Step C: for each detection, find the strongest overlapping kept
            detection; use contains → risk → length → priority to pick
            the winner.

Pure function: takes a detection list, returns a new list and a conflict
log. No mutation of inputs.
"""
from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from pii_masker.domain.detection import Detection
from pii_masker.domain.policy import MaskingPolicy
from pii_masker.domain.result import ConflictEntry
from pii_masker.resolve.dedup import dedup_exact
from pii_masker.resolve.priority import compute_score


@dataclass(frozen=True, slots=True)
class _Scored:
    """Internal scoring wrapper — NOT a domain type."""

    det: Detection
    priority: float

    @property
    def span_length(self) -> int:
        return self.det.span.length


def resolve(
    detections: Sequence[Detection],
    policy: MaskingPolicy,
) -> tuple[list[Detection], list[ConflictEntry]]:
    """Apply the full 5-layer conflict resolution pipeline.

    Returns `(kept, conflict_log)`. `conflict_log` contains one entry per
    losing detection.
    """
    if not detections:
        return [], []

    # Step 0: exact-duplicate dedup.
    deduped, conflict_log = dedup_exact(detections)

    # Step A: score everyone.
    scored = [_Scored(det=d, priority=compute_score(d, policy)) for d in deduped]

    # Step B: stable sort by (start, -length, -priority).
    scored.sort(key=lambda s: (s.det.span.start, -s.span_length, -s.priority))

    # Step C: greedy overlap resolution.
    kept: list[_Scored] = []
    for current in scored:
        overlapping = [k for k in kept if _overlaps(current, k)]
        if not overlapping:
            kept.append(current)
            continue

        # Pick the strongest opponent (by priority) among all overlapping
        # kept detections.
        strongest = max(overlapping, key=lambda k: k.priority)
        winner, loser, reason = _resolve_pair(current, strongest, policy)
        if winner is current:
            kept = [k for k in kept if k is not strongest]
            kept.append(current)
            conflict_log.append(
                ConflictEntry(winner=current.det, loser=strongest.det, reason=reason)
            )
        else:
            conflict_log.append(
                ConflictEntry(winner=strongest.det, loser=current.det, reason=reason)
            )

    return [s.det for s in kept], conflict_log


def _overlaps(a: _Scored, b: _Scored) -> bool:
    return a.det.span.overlaps(b.det.span)


def _contains(outer: _Scored, inner: _Scored) -> bool:
    """Strict containment — see `Span.contains` docstring."""
    return outer.det.span.contains(inner.det.span)


def _resolve_pair(
    a: _Scored, b: _Scored, policy: MaskingPolicy
) -> tuple[_Scored, _Scored, str]:
    """Decide a vs b using the 4-layer overlap matrix.

    1. Strict containment → longer wins
    2. Partial overlap: higher risk wins
    3. Same risk: longer span wins
    4. Same length: higher composite priority wins
    """
    if _contains(a, b):
        return (a, b, "CONTAINS:longer_wins")
    if _contains(b, a):
        return (b, a, "CONTAINS:longer_wins")

    risk_a = policy.risk_of(a.det.entity_type)
    risk_b = policy.risk_of(b.det.entity_type)
    if risk_a != risk_b:
        winner, loser = (a, b) if risk_a > risk_b else (b, a)
        w_risk = policy.risk_of(winner.det.entity_type)
        l_risk = policy.risk_of(loser.det.entity_type)
        return (winner, loser, f"RISK_LEVEL:{w_risk}>{l_risk}")

    if a.span_length != b.span_length:
        winner, loser = (a, b) if a.span_length > b.span_length else (b, a)
        return (
            winner,
            loser,
            f"SPAN_LENGTH:{winner.span_length}>{loser.span_length}",
        )

    winner, loser = (a, b) if a.priority >= b.priority else (b, a)
    return (
        winner,
        loser,
        f"PRIORITY_SCORE:{winner.priority:.1f}>={loser.priority:.1f}",
    )

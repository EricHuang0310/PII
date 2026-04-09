"""Step 0 — exact-duplicate dedup.

Ports v3/v4 `ConflictResolver.resolve` step 0:

> Exact Duplicate Dedup — `(start, end, entity_type)` completely identical
> triples are collapsed to the highest-scoring entry (ties keep first
> occurrence), handling CKIP × AddressEnhancedRecognizer duplicate detection
> of LOCATION.

Do not bypass this — it's the only layer that handles pure duplicates where
both detectors agree on the entity type and the exact span. Without it, the
later layers would resolve such pairs by arbitrary tiebreaks.

Return shape: `(deduped_detections, conflict_entries)` — the conflict
entries record which detections were collapsed, for audit.
"""
from __future__ import annotations

from collections.abc import Sequence

from pii_masker.domain.detection import Detection
from pii_masker.domain.result import ConflictEntry


def dedup_exact(
    detections: Sequence[Detection],
) -> tuple[list[Detection], list[ConflictEntry]]:
    """Collapse exact duplicates (same start, end, entity_type).

    Ties on confidence keep the FIRST occurrence — matching v3/v4. The
    conflict log records every dropped detection so the audit trail
    preserves them.
    """
    deduped: list[Detection] = []
    conflict_log: list[ConflictEntry] = []
    winner_by_key: dict[tuple[int, int, str], Detection] = {}

    for det in detections:
        key = (det.span.start, det.span.end, det.entity_type.value)
        existing = winner_by_key.get(key)
        if existing is None:
            winner_by_key[key] = det
            deduped.append(det)
            continue
        if det.confidence > existing.confidence:
            # New detection wins — existing loses
            conflict_log.append(
                ConflictEntry(
                    winner=det,
                    loser=existing,
                    reason="EXACT_DUP:higher_score_wins",
                )
            )
            winner_by_key[key] = det
            # Replace existing in deduped to preserve position
            deduped[deduped.index(existing)] = det
        else:
            reason = (
                "EXACT_DUP:higher_score_wins"
                if existing.confidence > det.confidence
                else "EXACT_DUP:first_wins"
            )
            conflict_log.append(
                ConflictEntry(winner=existing, loser=det, reason=reason)
            )

    return deduped, conflict_log

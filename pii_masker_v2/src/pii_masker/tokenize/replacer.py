"""Per-span, reverse-sorted token replacement.

Ports v3/v4 `_apply_per_span_replacement`. The algorithm:

1. Sort detections by `span.start` descending
2. For each detection, splice `text[:start] + token + text[end:]`

Reverse order is critical: replacing a later span doesn't shift the indices
of earlier ones. This is the v2 contract that closes Bug 1 from v3/v4 —
never use Presidio's `anonymize()` with entity-type-keyed operators because
that overwrites multiple same-type spans with a single value.

v2 API change: tokens is a `Mapping[span_id, str]` (keyed by
`Detection.span_id`, which is a stable UUID), not a dict keyed by entity
type. This is the type-system enforcement of the no-same-type-overwrite
invariant.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence

from pii_masker.domain.detection import Detection


def replace(
    text: str,
    detections: Sequence[Detection],
    tokens: Mapping[str, str],
) -> str:
    """Replace each detection's span with its token, in reverse order.

    Args:
        text: the normalized text to replace into
        detections: detections whose spans point into `text`
        tokens: mapping from `detection.span_id` to the replacement token

    Returns:
        A new string with every detection's span replaced by its token.
        If a detection's span_id is not in `tokens`, the detection is
        silently skipped (this should never happen in the normal pipeline —
        callers should always populate the token map for every detection).
    """
    # Sort by start descending so replacements don't shift earlier spans.
    sorted_dets = sorted(detections, key=lambda d: d.span.start, reverse=True)
    out = text
    for det in sorted_dets:
        token = tokens.get(det.span_id)
        if token is None:
            continue
        out = out[: det.span.start] + token + out[det.span.end :]
    return out

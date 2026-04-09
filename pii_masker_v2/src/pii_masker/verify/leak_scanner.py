"""Step 7 — fail-closed leak scanner (NEW in v2).

After masking, re-run the detector set on `masked_text`. Any detection whose
span is NOT inside a legitimate `[TOKEN]` is a LEAK — the masker missed
something and the output would expose PII to downstream consumers.

The scanner mirrors the main pipeline's detection-phase filters so it does
not flag PII that was DELIBERATELY not masked by policy:

- Applies the `MaskingPolicy.score_threshold` (same as the main pipeline)
- Drops `BRANCH` when `mask_branch_code=False`
- Applies `rules.conditional_amount` — an AMOUNT far from an account is
  allowed to leak, and the scanner respects that

The scanner returns a list of residual spans (empty = clean). The pipeline
converts a non-empty list into a `PIILeakError` by default.
"""
from __future__ import annotations

from collections.abc import Sequence

from pii_masker.detect.base import BaseDetector
from pii_masker.domain.detection import Detection
from pii_masker.domain.entity_type import EntityType
from pii_masker.domain.policy import MaskingPolicy
from pii_masker.rules import conditional_amount as rule_amount
from pii_masker.verify.token_regex import TOKEN_RE, span_is_inside_token


def scan(
    masked_text: str,
    detectors: Sequence[BaseDetector],
    policy: MaskingPolicy | None = None,
) -> list[Detection]:
    """Return detections in `masked_text` that are NOT inside masking tokens.

    Args:
        masked_text: the output of the main pipeline
        detectors: detector set to re-run (typically regex only, not NER)
        policy: if provided, the scanner applies the same filters the main
            pipeline used (score threshold, BRANCH drop, conditional AMOUNT).
            If None, the scanner returns ALL detections not inside tokens —
            useful for low-level tests.

    Returns:
        Empty list = clean mask. Non-empty = residual PII the masker should
        have caught.
    """
    if not masked_text:
        return []

    residual: list[Detection] = []
    for det in detectors:
        for d in det.detect(masked_text):
            if span_is_inside_token(masked_text, d.span.start, d.span.end):
                continue
            residual.append(d)

    if policy is None:
        return residual

    # Apply the same detection-phase filters the main pipeline uses so that
    # deliberately-unmasked entities aren't reported as leaks.
    filtered = [d for d in residual if d.confidence >= policy.score_threshold]
    if not policy.mask_branch_code:
        filtered = [d for d in filtered if d.entity_type is not EntityType.BRANCH]
    filtered = rule_amount.apply(filtered, policy.conditional_amount)
    return filtered


def strip_token_contents(masked_text: str) -> str:
    """Replace every `[TOKEN]` with spaces of equal length.

    Useful as a pre-pass before scanning: by blanking out token interiors we
    guarantee the detectors cannot match across a token boundary or on the
    token's own characters. Kept as a helper for callers that want a
    stricter scan path.
    """
    def _spaces(m: "object") -> str:
        match = m  # noqa: F841 - type hinting shim for mypy
        return " " * len(match.group(0))  # type: ignore[attr-defined]

    return TOKEN_RE.sub(_spaces, masked_text)

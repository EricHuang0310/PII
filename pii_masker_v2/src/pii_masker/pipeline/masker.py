"""MaskingPipeline — wires all 7 steps together.

Pipeline flow:

    Step 0:  normalize.compose.normalize(text)
    Step 1:  collect_detections(detectors, normalized_text)
    Step 2:  (no-op — detectors ARE the analyze step)
    Step 3:  rules.conditional_amount + rules.speaker_aware
    Step 4:  resolve.resolver.resolve
    Step 5:  tokenize.tracker.resolve + tokenize.replacer.replace
    Step 6:  usability.tagger.compute + audit sink writes
    Step 7:  verify.leak_scanner.scan (fail-closed by default)

The pipeline is instance-based so the detector list, policy, tracker, and
audit sink can all be constructed once and reused across many `mask()`
calls. A thin `mask(text, policy=...)` module function is provided for
one-shot usage.
"""
from __future__ import annotations

from collections.abc import Sequence
from typing import Optional

from pii_masker import __version__
from pii_masker.audit.event import AuditEvent
from pii_masker.audit.sinks.base import AuditSink
from pii_masker.audit.sinks.null_sink import NullAuditSink
from pii_masker.audit.trace import new_trace_id, new_turn_id
from pii_masker.config.loader import load_policy
from pii_masker.detect.base import BaseDetector
from pii_masker.detect.registry import build_all_detectors
from pii_masker.domain.detection import Detection
from pii_masker.domain.dialogue import Speaker
from pii_masker.domain.entity_type import EntityType
from pii_masker.domain.errors import PIILeakError
from pii_masker.domain.policy import MaskingPolicy
from pii_masker.domain.result import ConflictEntry, MaskingResult
from pii_masker.normalize.compose import normalize
from pii_masker.resolve import resolver as resolve_mod
from pii_masker.rules import conditional_amount as rule_amount
from pii_masker.rules import speaker_aware as rule_speaker
from pii_masker.tokenize.replacer import replace as token_replace
from pii_masker.tokenize.tracker import PseudonymTracker
from pii_masker.usability import tagger as usability_tagger
from pii_masker.usability.tags import UsabilityTag
from pii_masker.verify.leak_scanner import scan as leak_scan


class MaskingPipeline:
    """The full 7-step masking pipeline."""

    def __init__(
        self,
        *,
        policy: MaskingPolicy | None = None,
        detectors: Sequence[BaseDetector] | None = None,
        audit_sink: AuditSink | None = None,
        leak_scan_detectors: Sequence[BaseDetector] | None = None,
        include_ckip: bool = True,
        ckip_model: str = "bert-base",
        ckip_device: int = -1,
    ) -> None:
        self._policy: MaskingPolicy = policy or load_policy()
        if detectors is None:
            self._detectors: list[BaseDetector] = build_all_detectors(
                self._policy,
                ckip_model=ckip_model,
                ckip_device=ckip_device,
                include_ckip=include_ckip,
            )
        else:
            self._detectors = list(detectors)
        self._audit_sink: AuditSink = audit_sink or NullAuditSink()
        # Leak scanner uses a regex-only detector set by default — NER would
        # be both slow and lower-value for residual scanning (regex catches
        # the structured PII that actually matters for leakage).
        if leak_scan_detectors is None:
            from pii_masker.detect.registry import build_regex_detectors

            self._leak_detectors: list[BaseDetector] = build_regex_detectors(self._policy)
        else:
            self._leak_detectors = list(leak_scan_detectors)

    @property
    def policy(self) -> MaskingPolicy:
        return self._policy

    def close(self) -> None:
        self._audit_sink.close()

    def __enter__(self) -> "MaskingPipeline":
        return self

    def __exit__(self, *a: object) -> None:
        self.close()

    # ─── mask ────────────────────────────────────────────────────
    def mask(
        self,
        text: str,
        *,
        session_id: str = "",
        turn_id: str | None = None,
        trace_id: str | None = None,
        speaker: Speaker = Speaker.UNKNOWN,
        diarization_available: bool = False,
        tracker: PseudonymTracker | None = None,
        asr_confidence: float | None = None,
        fail_on_leak: bool = True,
    ) -> MaskingResult:
        """Run the full 7-step pipeline on one text."""
        if not text or not text.strip():
            return self._empty_result(session_id, turn_id or "", text)

        turn_id = turn_id or new_turn_id()
        trace_id = trace_id or new_trace_id()
        if tracker is None:
            tracker = PseudonymTracker(session_id=session_id)

        # Step 0: normalize
        normalized = normalize(text)

        # Step 1+2: detect
        raw: list[Detection] = []
        for d in self._detectors:
            raw.extend(d.detect(normalized))

        # Score threshold filter (was implicit in Presidio's analyze() call)
        raw = [d for d in raw if d.confidence >= self._policy.score_threshold]

        # mask_branch_code drops BRANCH unless the caller opts in
        if not self._policy.mask_branch_code:
            raw = [d for d in raw if d.entity_type is not EntityType.BRANCH]

        # Step 3: rules
        raw = rule_amount.apply(raw, self._policy.conditional_amount)
        raw = rule_speaker.apply(
            raw,
            text=normalized,
            diarization_available=diarization_available,
            policy=self._policy.diarization_fallback,
        )

        # Step 4: resolve
        resolved, conflict_log = resolve_mod.resolve(raw, self._policy)

        # Step 5: tokenize + replace
        tokens: dict[str, str] = {}
        for det in resolved:
            original = normalized[det.span.start : det.span.end]
            base_token = self._policy.token_for(det.entity_type)
            token = tracker.resolve(det.entity_type, original, base_token)
            tokens[det.span_id] = token

        masked_text = token_replace(normalized, resolved, tokens)

        # Step 6: usability + audit
        usability_tag, fallback_mode = usability_tagger.compute(
            text=text,
            detections=resolved,
            diarization_available=diarization_available,
            asr_confidence=asr_confidence,
            usability_policy=self._policy.usability,
            diarization_policy=self._policy.diarization_fallback,
        )
        self._write_audit(
            session_id=session_id,
            trace_id=trace_id,
            turn_id=turn_id,
            resolved=resolved,
            conflict_log=conflict_log,
            tokens=tokens,
            diarization_available=diarization_available,
            usability_tag=usability_tag,
        )

        # Step 7: leak scanner (fail-closed)
        leak_scan_passed = True
        residual = leak_scan(masked_text, self._leak_detectors, self._policy)
        if residual:
            leak_scan_passed = False
            if fail_on_leak:
                spans: tuple[tuple[int, int, str], ...] = tuple(
                    (d.span.start, d.span.end, d.entity_type.value) for d in residual
                )
                raise PIILeakError(
                    f"Residual PII detected in masked_text: {len(residual)} span(s)",
                    residual_spans=spans,
                )

        return MaskingResult.build(
            session_id=session_id,
            turn_id=turn_id,
            original_text=text,
            normalized_text=normalized,
            masked_text=masked_text,
            detections=resolved,
            tokens=tokens,
            pseudonym_map=tracker.get_mapping(),
            conflict_log=conflict_log,
            usability_tag=usability_tag,
            fallback_mode=fallback_mode,
            diarization_available=diarization_available,
            policy_version=self._policy.version,
            pipeline_version=__version__,
            leak_scan_passed=leak_scan_passed,
        )

    # ─── internal helpers ────────────────────────────────────────
    def _empty_result(
        self, session_id: str, turn_id: str, text: str
    ) -> MaskingResult:
        return MaskingResult.build(
            session_id=session_id,
            turn_id=turn_id,
            original_text=text,
            normalized_text=text,
            masked_text=text,
            detections=[],
            tokens={},
            pseudonym_map={},
            conflict_log=[],
            usability_tag=UsabilityTag.USABLE,
            fallback_mode=False,
            diarization_available=False,
            policy_version=self._policy.version,
            pipeline_version=__version__,
            leak_scan_passed=True,
        )

    def _write_audit(
        self,
        *,
        session_id: str,
        trace_id: str,
        turn_id: str,
        resolved: Sequence[Detection],
        conflict_log: Sequence[ConflictEntry],
        tokens: dict[str, str],
        diarization_available: bool,
        usability_tag: UsabilityTag,
    ) -> None:
        resolved_ids = {entry.winner.span_id for entry in conflict_log}
        for det in resolved:
            event = AuditEvent(
                session_id=session_id,
                trace_id=trace_id,
                turn_id=turn_id,
                step="Step1-5",
                rule_triggered=det.entity_type.value,
                entity_type=det.entity_type,
                entity_subtype=det.subtype or "",
                original_type_desc=det.entity_type.value,
                span_id=det.span_id,
                start=det.span.start,
                end=det.span.end,
                score=det.confidence,
                token_applied=tokens.get(det.span_id, ""),
                conflict_resolved=det.span_id in resolved_ids,
                diarization_available=diarization_available,
                usability_tag=usability_tag,
                detector_id=det.detector_id,
                policy_version=self._policy.version,
                pipeline_version=__version__,
            )
            self._audit_sink.write(event)


# ── Module-level convenience ────────────────────────────────────
_DEFAULT_PIPELINE: Optional[MaskingPipeline] = None


def mask(
    text: str,
    *,
    session_id: str = "",
    speaker: Speaker = Speaker.UNKNOWN,
    diarization_available: bool = False,
    tracker: PseudonymTracker | None = None,
    asr_confidence: float | None = None,
    fail_on_leak: bool = True,
    policy: MaskingPolicy | None = None,
) -> MaskingResult:
    """One-shot mask. Lazily instantiates a shared default pipeline.

    For production use, prefer constructing `MaskingPipeline` once and
    calling `.mask()` on it — that avoids re-building detectors per call.
    """
    global _DEFAULT_PIPELINE
    if _DEFAULT_PIPELINE is None or (policy is not None and policy is not _DEFAULT_PIPELINE.policy):
        _DEFAULT_PIPELINE = MaskingPipeline(policy=policy, include_ckip=False)
    return _DEFAULT_PIPELINE.mask(
        text,
        session_id=session_id,
        speaker=speaker,
        diarization_available=diarization_available,
        tracker=tracker,
        asr_confidence=asr_confidence,
        fail_on_leak=fail_on_leak,
    )

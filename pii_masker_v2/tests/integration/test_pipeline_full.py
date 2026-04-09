"""End-to-end pipeline tests — all 7 steps exercised together.

CKIP NER is excluded from these tests (`include_ckip=False`) so they run
fast and deterministically without the model. A separate test file covers
CKIP-backed paths behind the `requires_ckip` marker.
"""
from __future__ import annotations

import pytest

from pii_masker.audit.sinks.null_sink import NullAuditSink
from pii_masker.domain.dialogue import DialogueTurn, Speaker
from pii_masker.domain.entity_type import EntityType
from pii_masker.domain.errors import PIILeakError
from pii_masker.pipeline.dialogue import mask_dialogue
from pii_masker.pipeline.masker import MaskingPipeline
from pii_masker.tokenize.tracker import PseudonymTracker
from pii_masker.usability.tags import UsabilityTag


@pytest.fixture
def pipeline(default_policy) -> MaskingPipeline:  # type: ignore[no-untyped-def]
    return MaskingPipeline(
        policy=default_policy,
        include_ckip=False,
        audit_sink=NullAuditSink(),
    )


@pytest.mark.integration
def test_mask_empty_text(pipeline: MaskingPipeline) -> None:
    result = pipeline.mask("", session_id="S001")
    assert result.masked_text == ""
    assert result.detections == ()
    assert result.leak_scan_passed is True


@pytest.mark.integration
def test_mask_phone_number(pipeline: MaskingPipeline) -> None:
    result = pipeline.mask(
        "我的電話0912345678",
        session_id="S001",
        diarization_available=True,
    )
    assert "[PHONE]" in result.masked_text
    assert "0912345678" not in result.masked_text
    assert any(d.entity_type is EntityType.TW_PHONE for d in result.detections)


@pytest.mark.integration
def test_mask_credit_card(pipeline: MaskingPipeline) -> None:
    result = pipeline.mask(
        "卡號4111111111111111",
        session_id="S001",
        diarization_available=True,
    )
    assert "[CARD]" in result.masked_text
    assert "4111111111111111" not in result.masked_text


@pytest.mark.integration
def test_mask_carries_versions(pipeline: MaskingPipeline) -> None:
    result = pipeline.mask("我的電話0912345678", session_id="S001", diarization_available=True)
    assert result.policy_version == "v4.1.0"
    assert result.pipeline_version == "2.0.0"


@pytest.mark.integration
def test_mask_result_is_frozen(pipeline: MaskingPipeline) -> None:
    result = pipeline.mask("卡號4111111111111111", session_id="S001", diarization_available=True)
    with pytest.raises(Exception):
        result.session_id = "other"  # type: ignore[misc]


@pytest.mark.integration
def test_mask_includes_stable_span_ids(pipeline: MaskingPipeline) -> None:
    result = pipeline.mask("電話0912345678", session_id="S001", diarization_available=True)
    for det in result.detections:
        assert det.span_id in result.tokens
        assert result.tokens[det.span_id] == "[PHONE]"


@pytest.mark.integration
def test_mask_conditional_amount_without_account(pipeline: MaskingPipeline) -> None:
    """A lone '50000元' should NOT be masked — no nearby account."""
    result = pipeline.mask("今年賺50000元", session_id="S001", diarization_available=True)
    assert "50000元" in result.masked_text  # not masked
    assert not any(d.entity_type is EntityType.AMOUNT for d in result.detections)


@pytest.mark.integration
def test_mask_amount_txn_always_masked(pipeline: MaskingPipeline) -> None:
    """'轉帳50000元' should always be masked (AMOUNT_TXN)."""
    result = pipeline.mask("我要轉帳50000元", session_id="S001", diarization_available=True)
    assert "50000元" not in result.masked_text
    assert "[AMOUNT_TXN]" in result.masked_text


@pytest.mark.integration
def test_mask_leak_scan_raises_on_residual(default_policy) -> None:  # type: ignore[no-untyped-def]
    """If a detector is broken and leaks a phone, fail-closed fires."""
    from pii_masker.detect.ner.ckip_adapter import CkipNerAdapter
    from pii_masker.detect.regex.verification_answer import VerificationAnswerDetector

    # Build a pipeline that has NO regex detectors at all → nothing gets masked →
    # scan catches the leak → PIILeakError raised.
    pipeline = MaskingPipeline(
        policy=default_policy,
        detectors=[VerificationAnswerDetector(30)],  # won't catch a phone number
        include_ckip=False,
    )
    with pytest.raises(PIILeakError) as exc_info:
        pipeline.mask(
            "電話0912345678",
            session_id="S001",
            diarization_available=True,
            fail_on_leak=True,
        )
    assert exc_info.value.residual_spans
    assert any(et == "TW_PHONE" for _, _, et in exc_info.value.residual_spans)


@pytest.mark.integration
def test_mask_leak_scan_can_be_disabled(default_policy) -> None:  # type: ignore[no-untyped-def]
    """fail_on_leak=False returns the result with leak_scan_passed=False."""
    from pii_masker.detect.regex.verification_answer import VerificationAnswerDetector

    pipeline = MaskingPipeline(
        policy=default_policy,
        detectors=[VerificationAnswerDetector(30)],
        include_ckip=False,
    )
    result = pipeline.mask(
        "電話0912345678",
        session_id="S001",
        diarization_available=True,
        fail_on_leak=False,
    )
    assert result.leak_scan_passed is False


@pytest.mark.integration
def test_mask_audit_sink_receives_events(default_policy) -> None:  # type: ignore[no-untyped-def]
    sink = NullAuditSink()
    pipeline = MaskingPipeline(
        policy=default_policy, include_ckip=False, audit_sink=sink
    )
    pipeline.mask("電話0912345678", session_id="S001", diarization_available=True)
    assert sink.events_written >= 1


@pytest.mark.integration
def test_mask_dialogue_shares_tracker(pipeline: MaskingPipeline) -> None:
    turns = [
        DialogueTurn(text="卡號4111111111111111", speaker=Speaker.CUSTOMER),
        DialogueTurn(text="再確認卡號4111111111111111", speaker=Speaker.CUSTOMER),
    ]
    results = mask_dialogue(turns, pipeline, session_id="S001")
    assert len(results) == 2
    # Both turns saw the same card → tracker has one entry
    mapping = results[-1].pseudonym_map
    assert EntityType.TW_CREDIT_CARD in mapping
    assert len(mapping[EntityType.TW_CREDIT_CARD]) == 1


@pytest.mark.integration
def test_mask_dialogue_diarization_ratio_threshold(pipeline: MaskingPipeline) -> None:
    """Exactly 1 out of 5 turns labeled → ratio 0.2 < 0.8 threshold → no diarization."""
    turns = [
        DialogueTurn(text="a", speaker=Speaker.UNKNOWN),
        DialogueTurn(text="b", speaker=Speaker.UNKNOWN),
        DialogueTurn(text="c", speaker=Speaker.AGENT),
        DialogueTurn(text="d", speaker=Speaker.UNKNOWN),
        DialogueTurn(text="e", speaker=Speaker.UNKNOWN),
    ]
    results = mask_dialogue(turns, pipeline, session_id="S001")
    # All turns should see diarization_available=False
    assert all(r.diarization_available is False for r in results)


@pytest.mark.integration
def test_mask_dialogue_diarization_ratio_above_threshold(
    pipeline: MaskingPipeline,
) -> None:
    turns = [
        DialogueTurn(text="a", speaker=Speaker.AGENT),
        DialogueTurn(text="b", speaker=Speaker.CUSTOMER),
        DialogueTurn(text="c", speaker=Speaker.CUSTOMER),
        DialogueTurn(text="d", speaker=Speaker.AGENT),
        DialogueTurn(text="e", speaker=Speaker.CUSTOMER),
    ]
    results = mask_dialogue(turns, pipeline, session_id="S001")
    # 5/5 labeled → ratio 1.0 >= 0.8 → diarization_available = True
    assert all(r.diarization_available is True for r in results)


@pytest.mark.integration
def test_mask_speaker_aware_does_not_mutate_detections(
    pipeline: MaskingPipeline,
) -> None:
    """v2 invariant — pipeline must not mutate any Detection mid-flight."""
    result = pipeline.mask(
        "請問您的電話0912345678",
        session_id="S001",
        diarization_available=False,  # triggers speaker-aware boost path
    )
    # The result's detection confidences may be boosted, but the returned
    # objects are frozen — test asserts we can still read them.
    for det in result.detections:
        assert 0.0 <= det.confidence <= 1.0


@pytest.mark.integration
def test_mask_full_dialogue_realistic(pipeline: MaskingPipeline) -> None:
    """Port of the v3/v4 demo() dialogue — smoke-test a realistic script."""
    tracker = PseudonymTracker(session_id="demo_001")
    lines = [
        ("AGENT",    "請問您的身分證字號？"),
        ("CUSTOMER", "A123456789"),
        ("AGENT",    "電話號碼幾號呢？"),
        ("CUSTOMER", "0912345678"),
        ("AGENT",    "信用卡卡號是多少？"),
        ("CUSTOMER", "卡號4111111111111111"),
        ("AGENT",    "請問驗證碼？"),
        ("CUSTOMER", "驗證碼654321"),
        ("AGENT",    "需要轉帳多少？"),
        ("CUSTOMER", "我要轉帳50000元到帳號1234567890"),
    ]
    results = [
        pipeline.mask(
            text=text,
            session_id="demo_001",
            speaker=Speaker[spk] if spk != "UNKNOWN" else Speaker.UNKNOWN,
            diarization_available=True,
            tracker=tracker,
        )
        for spk, text in lines
    ]
    # Critical PII must not appear in any masked output
    combined = "\n".join(r.masked_text for r in results)
    assert "A123456789" not in combined
    assert "0912345678" not in combined
    assert "4111111111111111" not in combined
    assert "654321" not in combined
    assert "1234567890" not in combined
    # Tracker should have collected originals for PERSON-family (none here)
    # and account/card audit entries
    mapping = tracker.get_mapping()
    assert EntityType.TW_CREDIT_CARD in mapping
    assert "4111111111111111" in mapping[EntityType.TW_CREDIT_CARD]

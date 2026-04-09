"""Standalone v2 dialogue demo — shares a PseudonymTracker across turns.

Run with:
    cd pii_masker_v2
    python examples/demo_dialogue.py
"""
from __future__ import annotations

from pii_masker.audit.sinks.null_sink import NullAuditSink
from pii_masker.config.loader import load_policy
from pii_masker.domain.dialogue import DialogueTurn, Speaker
from pii_masker.pipeline.dialogue import mask_dialogue
from pii_masker.pipeline.masker import MaskingPipeline


def main() -> None:
    turns = [
        DialogueTurn(text="請問您的大名是？", speaker=Speaker.AGENT),
        DialogueTurn(text="王小明", speaker=Speaker.CUSTOMER),
        DialogueTurn(text="請問您的身分證字號？", speaker=Speaker.AGENT),
        DialogueTurn(text="A123456789", speaker=Speaker.CUSTOMER),
        DialogueTurn(text="電話號碼幾號呢？", speaker=Speaker.AGENT),
        DialogueTurn(text="0912345678", speaker=Speaker.CUSTOMER),
        DialogueTurn(text="信用卡卡號是多少？", speaker=Speaker.AGENT),
        DialogueTurn(text="卡號4111111111111111", speaker=Speaker.CUSTOMER),
        DialogueTurn(text="需要轉帳多少？", speaker=Speaker.AGENT),
        DialogueTurn(
            text="我要轉帳50000元到帳號1234567890",
            speaker=Speaker.CUSTOMER,
        ),
    ]

    pipeline = MaskingPipeline(
        policy=load_policy(),
        include_ckip=False,
        audit_sink=NullAuditSink(),
    )

    results = mask_dialogue(turns, pipeline, session_id="demo_001")

    print("=" * 70)
    print("  pii_masker v2 — dialogue demo")
    print("=" * 70)
    for i, (turn, result) in enumerate(zip(turns, results), 1):
        print(f"\n[{i:02d}] {turn.speaker.value}")
        print(f"  in:  {turn.text}")
        print(f"  out: {result.masked_text}")

    print("\n" + "=" * 70)
    print("  pseudonym_map (audit trail)")
    print("=" * 70)
    last = results[-1]
    for et, originals in last.pseudonym_map.items():
        for orig, token in originals.items():
            print(f"  {et.value}: {orig} → {token}")


if __name__ == "__main__":
    main()

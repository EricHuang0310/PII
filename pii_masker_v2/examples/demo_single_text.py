"""Standalone v2 demo — masks a single text string.

Run with:
    cd pii_masker_v2
    python examples/demo_single_text.py
"""
from __future__ import annotations

from pii_masker.audit.sinks.jsonl_sink import JsonlAuditSink
from pii_masker.config.loader import load_policy
from pii_masker.pipeline.masker import MaskingPipeline


def main() -> None:
    policy = load_policy()
    # CKIP disabled so this demo runs without the model dependency.
    with MaskingPipeline(
        policy=policy,
        include_ckip=False,
        audit_sink=JsonlAuditSink("demo_audit_log.jsonl"),
    ) as pipeline:
        inputs = [
            "我的電話是0912345678",
            "卡號4111111111111111",
            "身分證A123456789",
            "我要轉帳50000元到帳號1234567890",
            "生日是民國七十四年五月一日",
        ]
        for text in inputs:
            result = pipeline.mask(
                text=text,
                session_id="demo",
                diarization_available=True,
            )
            print(f"  {text}")
            print(f"→ {result.masked_text}")
            print(f"  tags: {[d.entity_type.value for d in result.detections]}")
            print(f"  leak_scan_passed: {result.leak_scan_passed}")
            print()

    print("Audit log → demo_audit_log.jsonl")


if __name__ == "__main__":
    main()

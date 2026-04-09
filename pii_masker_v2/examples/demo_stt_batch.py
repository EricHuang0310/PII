"""Standalone STT batch demo — reads JSON files from a directory.

Run with:
    cd pii_masker_v2
    python examples/demo_stt_batch.py path/to/stt_json_dir
"""
from __future__ import annotations

import sys
from pathlib import Path

from pii_masker.audit.sinks.jsonl_sink import JsonlAuditSink
from pii_masker.config.loader import load_policy
from pii_masker.io.stt_json_loader import iter_stt_dir
from pii_masker.pipeline.dialogue import mask_dialogue
from pii_masker.pipeline.masker import MaskingPipeline


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print("Usage: python examples/demo_stt_batch.py <stt_json_dir>", file=sys.stderr)
        return 2
    stt_dir = Path(argv[1])
    if not stt_dir.is_dir():
        print(f"Not a directory: {stt_dir}", file=sys.stderr)
        return 2

    pipeline = MaskingPipeline(
        policy=load_policy(),
        include_ckip=False,
        audit_sink=JsonlAuditSink("stt_audit.jsonl"),
    )
    with pipeline:
        for json_path, turns in iter_stt_dir(stt_dir):
            session_id = json_path.stem
            results = mask_dialogue(turns, pipeline, session_id=session_id)
            print(
                f"{json_path.name}: {len(turns)} turns → "
                f"{sum(r.entity_count for r in results)} detections, "
                f"all leak_scan_passed: {all(r.leak_scan_passed for r in results)}"
            )
    print("\nAudit → stt_audit.jsonl")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))

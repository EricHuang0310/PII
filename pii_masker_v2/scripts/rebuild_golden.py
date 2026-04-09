#!/usr/bin/env python
"""Rebuild the golden expected file from the current v2 pipeline.

Usage:
    python scripts/rebuild_golden.py

Intentionally NOT a test fixture auto-regeneration — this is a manual
tool. Running it is an explicit decision to lock in whatever the v2
pipeline currently produces as the new regression baseline.

Commit both `tests/golden/fixtures/bank_dialogue.json` (inputs) AND
`tests/golden/expected_v4/bank_dialogue.json` (outputs) together.
"""
from __future__ import annotations

import json
from pathlib import Path

from pii_masker.audit.sinks.null_sink import NullAuditSink
from pii_masker.config.loader import load_policy
from pii_masker.pipeline.masker import MaskingPipeline

_REPO_ROOT = Path(__file__).resolve().parent.parent
_FIXTURES = _REPO_ROOT / "tests" / "golden" / "fixtures" / "bank_dialogue.json"
_EXPECTED = _REPO_ROOT / "tests" / "golden" / "expected_v4" / "bank_dialogue.json"


def main() -> None:
    fixtures = json.loads(_FIXTURES.read_text(encoding="utf-8"))["cases"]
    policy = load_policy()
    pipeline = MaskingPipeline(
        policy=policy,
        include_ckip=False,
        audit_sink=NullAuditSink(),
    )

    expected: dict[str, dict[str, object]] = {}
    for case in fixtures:
        name = case["name"]
        text = case["text"]
        result = pipeline.mask(
            text=text, session_id=f"golden-{name}", diarization_available=True
        )
        expected[name] = {
            "masked_text": result.masked_text,
            "entity_types": sorted(t.value for t in result.entity_types),
            "detection_count": len(result.detections),
            "leak_scan_passed": result.leak_scan_passed,
            "policy_version": result.policy_version,
            "pipeline_version": result.pipeline_version,
        }
        print(f"  [{name}] {text!r} → {result.masked_text!r}")

    _EXPECTED.parent.mkdir(parents=True, exist_ok=True)
    _EXPECTED.write_text(
        json.dumps(expected, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(f"\nWrote {len(expected)} golden cases → {_EXPECTED}")


if __name__ == "__main__":
    main()

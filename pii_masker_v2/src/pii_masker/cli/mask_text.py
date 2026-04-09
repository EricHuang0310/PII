"""`pii-masker mask-text` — one-shot mask of a command-line string."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from pii_masker.audit.sinks.jsonl_sink import JsonlAuditSink
from pii_masker.audit.sinks.null_sink import NullAuditSink
from pii_masker.config.loader import load_policy
from pii_masker.pipeline.masker import MaskingPipeline


def add_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("text", help="Text to mask (wrap in quotes if it contains spaces)")
    parser.add_argument(
        "--policy",
        type=Path,
        default=None,
        help="Path to a policy YAML (defaults to packaged policy/defaults.yaml)",
    )
    parser.add_argument(
        "--audit",
        type=Path,
        default=None,
        help="Optional JSONL audit sink path",
    )
    parser.add_argument(
        "--include-ckip",
        action="store_true",
        help="Include CKIP NER (requires ckip-transformers + torch)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit the full MaskingResult as JSON to stdout",
    )
    parser.add_argument(
        "--session",
        default="cli",
        help="Session ID for audit rows (default: cli)",
    )
    parser.add_argument(
        "--diarization",
        action="store_true",
        help="Claim diarization is available (default: false)",
    )


def run(args: argparse.Namespace) -> int:
    policy = load_policy(args.policy)
    sink = JsonlAuditSink(args.audit) if args.audit else NullAuditSink()
    pipeline = MaskingPipeline(
        policy=policy,
        include_ckip=args.include_ckip,
        audit_sink=sink,
    )
    with pipeline:
        result = pipeline.mask(
            text=args.text,
            session_id=args.session,
            diarization_available=args.diarization,
        )

    if args.json:
        out = {
            "masked_text": result.masked_text,
            "normalized_text": result.normalized_text,
            "entities_found": [d.to_dict() for d in result.detections],
            "tokens": dict(result.tokens),
            "usability_tag": result.usability_tag.value,
            "leak_scan_passed": result.leak_scan_passed,
            "policy_version": result.policy_version,
            "pipeline_version": result.pipeline_version,
        }
        json.dump(out, sys.stdout, ensure_ascii=False, indent=2)
        sys.stdout.write("\n")
    else:
        sys.stdout.write(result.masked_text + "\n")
    return 0

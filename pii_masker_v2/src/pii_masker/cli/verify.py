"""`pii-masker verify` — scan a text file / JSONL audit for residual PII."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from pii_masker.config.loader import load_policy
from pii_masker.detect.registry import build_regex_detectors
from pii_masker.verify.leak_scanner import scan


def add_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "input",
        type=Path,
        help="File to scan: plain text, or JSONL with `masked_text` field",
    )
    parser.add_argument("--policy", type=Path, default=None)
    parser.add_argument(
        "--field",
        default="masked_text",
        help="For JSONL inputs, which field to scan (default: masked_text)",
    )


def run(args: argparse.Namespace) -> int:
    if not args.input.exists():
        print(f"Error: input file not found: {args.input}", file=sys.stderr)
        return 2

    policy = load_policy(args.policy)
    detectors = build_regex_detectors(policy)

    texts: list[tuple[str, str]] = []  # (label, text)
    if args.input.suffix == ".jsonl":
        for i, line in enumerate(
            args.input.read_text(encoding="utf-8").splitlines()
        ):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as e:
                print(
                    f"Skipping malformed JSONL line {i + 1}: {e}",
                    file=sys.stderr,
                )
                continue
            text = row.get(args.field, "")
            if text:
                texts.append((f"line {i + 1}", text))
    else:
        texts.append((str(args.input), args.input.read_text(encoding="utf-8")))

    total_leaks = 0
    for label, text in texts:
        residual = scan(text, detectors, policy)
        for d in residual:
            print(
                f"[LEAK] {label} {d.entity_type.value} "
                f"@ [{d.span.start}:{d.span.end}] "
                f"raw={d.raw_text!r} "
                f"detector={d.detector_id}"
            )
            total_leaks += 1

    if total_leaks == 0:
        print(f"OK: 0 leaks detected across {len(texts)} input(s)")
        return 0

    print(f"FAIL: {total_leaks} residual PII instance(s) found", file=sys.stderr)
    return 1

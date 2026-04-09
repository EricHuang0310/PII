"""`pii-masker mask-csv` — mask a column of a CSV file."""
from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

from pii_masker.audit.sinks.jsonl_sink import JsonlAuditSink
from pii_masker.audit.sinks.null_sink import NullAuditSink
from pii_masker.config.loader import load_policy
from pii_masker.pipeline.masker import MaskingPipeline


def add_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("input", type=Path, help="Input CSV path")
    parser.add_argument(
        "--column",
        required=True,
        help="Name of the column containing text to mask",
    )
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="Output CSV path (adds a column `{column}_masked`)",
    )
    parser.add_argument("--policy", type=Path, default=None)
    parser.add_argument("--audit", type=Path, default=None)
    parser.add_argument("--include-ckip", action="store_true")
    parser.add_argument(
        "--encoding", default="utf-8", help="CSV encoding (default: utf-8)"
    )
    parser.add_argument(
        "--diarization",
        action="store_true",
        help="Claim diarization is available for all rows",
    )


def run(args: argparse.Namespace) -> int:
    if not args.input.exists():
        print(f"Error: input file not found: {args.input}", file=sys.stderr)
        return 2

    policy = load_policy(args.policy)
    sink = JsonlAuditSink(args.audit) if args.audit else NullAuditSink()
    pipeline = MaskingPipeline(
        policy=policy,
        include_ckip=args.include_ckip,
        audit_sink=sink,
    )

    rows_in = 0
    rows_out = 0

    with args.input.open(encoding=args.encoding, newline="") as f_in:
        reader = csv.DictReader(f_in)
        if args.column not in (reader.fieldnames or []):
            print(
                f"Error: column {args.column!r} not in input CSV "
                f"(available: {reader.fieldnames})",
                file=sys.stderr,
            )
            return 2

        masked_col = f"{args.column}_masked"
        fieldnames = list(reader.fieldnames or []) + [masked_col]

        with args.output.open(
            "w", encoding=args.encoding, newline=""
        ) as f_out:
            writer = csv.DictWriter(f_out, fieldnames=fieldnames)
            writer.writeheader()

            with pipeline:
                for row in reader:
                    rows_in += 1
                    text = row.get(args.column, "") or ""
                    result = pipeline.mask(
                        text=text,
                        session_id=f"csv-row-{rows_in}",
                        diarization_available=args.diarization,
                    )
                    row[masked_col] = result.masked_text
                    writer.writerow(row)
                    rows_out += 1

    print(f"Masked {rows_out}/{rows_in} rows → {args.output}")
    return 0

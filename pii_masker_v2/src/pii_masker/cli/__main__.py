"""`python -m pii_masker` — dispatches to subcommands."""
from __future__ import annotations

import argparse
import sys
from typing import Sequence

from pii_masker.cli import mask_text as mask_text_cli
from pii_masker.cli import mask_csv as mask_csv_cli
from pii_masker.cli import verify as verify_cli


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="pii-masker",
        description="Taiwanese-bank voice/STT PII masking pipeline (v2).",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    mt = sub.add_parser("mask-text", help="Mask a single text string")
    mask_text_cli.add_arguments(mt)
    mt.set_defaults(func=mask_text_cli.run)

    mc = sub.add_parser("mask-csv", help="Mask rows from a CSV file")
    mask_csv_cli.add_arguments(mc)
    mc.set_defaults(func=mask_csv_cli.run)

    ve = sub.add_parser("verify", help="Scan an audit file for residual PII")
    verify_cli.add_arguments(ve)
    ve.set_defaults(func=verify_cli.run)

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args) or 0)


if __name__ == "__main__":
    sys.exit(main())

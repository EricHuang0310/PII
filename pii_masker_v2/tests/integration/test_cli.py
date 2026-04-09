"""CLI integration tests."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from pii_masker.cli.__main__ import main


@pytest.mark.integration
def test_cli_mask_text_basic(capsys: pytest.CaptureFixture[str]) -> None:
    code = main(["mask-text", "我的電話是0912345678", "--diarization"])
    assert code == 0
    captured = capsys.readouterr()
    assert "[PHONE]" in captured.out
    assert "0912345678" not in captured.out


@pytest.mark.integration
def test_cli_mask_text_json_output(capsys: pytest.CaptureFixture[str]) -> None:
    code = main(
        ["mask-text", "卡號4111111111111111", "--diarization", "--json"]
    )
    assert code == 0
    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert "[CARD]" in payload["masked_text"]
    assert payload["leak_scan_passed"] is True
    assert payload["policy_version"]
    assert payload["pipeline_version"] == "2.0.0"


@pytest.mark.integration
def test_cli_mask_csv(tmp_path: Path) -> None:
    import csv as _csv

    input_csv = tmp_path / "in.csv"
    input_csv.write_text(
        "id,文本\n1,電話0912345678\n2,卡號4111111111111111\n",
        encoding="utf-8",
    )
    output_csv = tmp_path / "out.csv"

    code = main(
        [
            "mask-csv",
            str(input_csv),
            "--column", "文本",
            "--output", str(output_csv),
            "--diarization",
        ]
    )
    assert code == 0

    with output_csv.open(encoding="utf-8", newline="") as f:
        rows = list(_csv.DictReader(f))
    assert len(rows) == 2
    # Original column preserved for audit trail; masked column has the token
    assert "文本_masked" in rows[0]
    assert rows[0]["文本"] == "電話0912345678"
    assert "[PHONE]" in rows[0]["文本_masked"]
    assert "0912345678" not in rows[0]["文本_masked"]
    assert rows[1]["文本"] == "卡號4111111111111111"
    assert "[CARD]" in rows[1]["文本_masked"]
    assert "4111111111111111" not in rows[1]["文本_masked"]


@pytest.mark.integration
def test_cli_verify_clean_file(tmp_path: Path) -> None:
    clean = tmp_path / "clean.txt"
    clean.write_text("我叫[NAME]卡號[CARD]電話[PHONE]", encoding="utf-8")
    code = main(["verify", str(clean)])
    assert code == 0


@pytest.mark.integration
def test_cli_verify_leaked_file(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    leaked = tmp_path / "leaked.txt"
    leaked.write_text("電話0912345678", encoding="utf-8")
    code = main(["verify", str(leaked)])
    assert code == 1
    err = capsys.readouterr().err
    assert "FAIL" in err


@pytest.mark.integration
def test_cli_verify_jsonl(tmp_path: Path) -> None:
    jsonl = tmp_path / "audit.jsonl"
    jsonl.write_text(
        '{"masked_text": "我叫[NAME]"}\n'
        '{"masked_text": "卡號[CARD]"}\n',
        encoding="utf-8",
    )
    code = main(["verify", str(jsonl)])
    assert code == 0

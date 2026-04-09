"""Tests for the STT JSON loader."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from pii_masker.domain.dialogue import Speaker
from pii_masker.io.stt_json_loader import load_stt_json


@pytest.mark.integration
def test_stt_loader_inbound_direction(tmp_path: Path) -> None:
    """Inbound (I): R1 = AGENT, R0 = CUSTOMER."""
    path = tmp_path / "call.json"
    path.write_text(
        json.dumps(
            {
                "DIALOGUE_INFO": {"DIRECTION": "I"},
                "SEGMENTS": [
                    {"role": "R1", "text": "請問您的電話", "start": 0.0, "end": 1.5, "confidence": 0.95},
                    {"role": "R0", "text": "0912345678", "start": 1.6, "end": 3.0, "confidence": 0.88},
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    turns = load_stt_json(path)
    assert len(turns) == 2
    assert turns[0].speaker is Speaker.AGENT
    assert turns[1].speaker is Speaker.CUSTOMER
    assert turns[1].text == "0912345678"
    assert turns[1].asr_confidence == pytest.approx(0.88)


@pytest.mark.integration
def test_stt_loader_outbound_direction(tmp_path: Path) -> None:
    """Outbound (O): R0 = AGENT, R1 = CUSTOMER."""
    path = tmp_path / "call.json"
    path.write_text(
        json.dumps(
            {
                "DIALOGUE_INFO": {"DIRECTION": "O"},
                "SEGMENTS": [
                    {"role": "R0", "text": "您好這裡是銀行", "start": 0.0, "end": 1.5},
                    {"role": "R1", "text": "您好", "start": 1.6, "end": 2.0},
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    turns = load_stt_json(path)
    assert turns[0].speaker is Speaker.AGENT
    assert turns[1].speaker is Speaker.CUSTOMER


@pytest.mark.integration
def test_stt_loader_unknown_direction(tmp_path: Path) -> None:
    path = tmp_path / "call.json"
    path.write_text(
        json.dumps(
            {
                "DIALOGUE_INFO": {},
                "SEGMENTS": [
                    {"role": "R0", "text": "x"},
                    {"role": "R1", "text": "y"},
                ],
            },
        ),
        encoding="utf-8",
    )
    turns = load_stt_json(path)
    assert turns[0].speaker is Speaker.UNKNOWN
    assert turns[1].speaker is Speaker.UNKNOWN

"""STT JSON loader — reads a directory of STT transcripts and yields DialogueTurns.

Ports the DIALOGUE_INFO.DIRECTION speaker mapping from the root `run_stt.py`:

- DIRECTION 'I' (inbound)  → R1 = AGENT,    R0 = CUSTOMER
- DIRECTION 'O' (outbound) → R0 = AGENT,    R1 = CUSTOMER

Expected STT JSON structure (flexible — many keys are optional):

    {
      "DIALOGUE_INFO": {"DIRECTION": "I"},
      "SEGMENTS": [
        {"role": "R0", "text": "...", "start": 0.0, "end": 1.5, "confidence": 0.92},
        ...
      ]
    }
"""
from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path

from pii_masker.domain.dialogue import DialogueTurn, Speaker


def _role_map(direction: str) -> dict[str, Speaker]:
    if direction.upper() == "I":
        return {"R0": Speaker.CUSTOMER, "R1": Speaker.AGENT}
    if direction.upper() == "O":
        return {"R0": Speaker.AGENT, "R1": Speaker.CUSTOMER}
    return {"R0": Speaker.UNKNOWN, "R1": Speaker.UNKNOWN}


def load_stt_json(path: Path) -> list[DialogueTurn]:
    """Load one STT JSON file into a list of DialogueTurns."""
    data = json.loads(path.read_text(encoding="utf-8"))
    direction = data.get("DIALOGUE_INFO", {}).get("DIRECTION", "")
    role_to_speaker = _role_map(direction)

    segments = data.get("SEGMENTS", [])
    turns: list[DialogueTurn] = []
    for seg in segments:
        role = seg.get("role", "")
        speaker = role_to_speaker.get(role, Speaker.UNKNOWN)
        turns.append(
            DialogueTurn(
                text=seg.get("text", ""),
                speaker=speaker,
                start_time=seg.get("start"),
                end_time=seg.get("end"),
                asr_confidence=seg.get("confidence"),
                turn_id=seg.get("id", ""),
            )
        )
    return turns


def iter_stt_dir(directory: Path) -> Iterator[tuple[Path, list[DialogueTurn]]]:
    """Yield (path, turns) for every *.json file in `directory`."""
    for p in sorted(directory.glob("*.json")):
        yield p, load_stt_json(p)

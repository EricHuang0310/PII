"""Golden regression tests for the v2 pipeline.

**Scope**: These tests lock in the current v2 output behavior on a canonical
corpus of regex-detectable bank dialogue cases. They do NOT verify
byte-exact parity with the root `pipeline.py` — true cross-pipeline parity
requires CKIP Transformers and Presidio, which are not assumed installed in
CI. When those are available, add a parallel test file that loads the root
pipeline as an oracle and diffs its output against v2's.

**Contract**: Each case in `fixtures/bank_dialogue.json` asserts:
1. The masked_text matches the recorded golden output byte-exact
2. The set of entity types in the result matches `expected_types`
3. The leak scanner passes

Updating these tests requires an explicit intent — never silently
regenerate the golden file. If behavior changes for a legitimate reason,
update `fixtures/expected_v4.json` and commit it with a clear rationale.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from pii_masker.audit.sinks.null_sink import NullAuditSink
from pii_masker.pipeline.masker import MaskingPipeline

_GOLDEN_DIR = Path(__file__).resolve().parent
_FIXTURES = _GOLDEN_DIR / "fixtures" / "bank_dialogue.json"
_EXPECTED = _GOLDEN_DIR / "expected_v4" / "bank_dialogue.json"


def _load_fixtures() -> list[dict[str, object]]:
    data = json.loads(_FIXTURES.read_text(encoding="utf-8"))
    return data["cases"]


@pytest.fixture(scope="module")
def pipeline(default_policy) -> MaskingPipeline:  # type: ignore[no-untyped-def]
    return MaskingPipeline(
        policy=default_policy,
        include_ckip=False,
        audit_sink=NullAuditSink(),
    )


@pytest.mark.golden
@pytest.mark.parametrize(
    "case", _load_fixtures(), ids=lambda c: c["name"]
)
def test_golden_case(
    case: dict[str, object], pipeline: MaskingPipeline
) -> None:
    """Every fixture case must produce byte-exact golden output."""
    if not _EXPECTED.exists():
        pytest.skip(
            "Golden expected file missing. Run scripts/rebuild_golden.py "
            "or set PII_MASKER_REBUILD_GOLDEN=1 to generate."
        )
    expected_all = json.loads(_EXPECTED.read_text(encoding="utf-8"))
    name = case["name"]
    assert name in expected_all, f"no recorded expected output for case {name!r}"
    expected = expected_all[name]

    result = pipeline.mask(
        text=case["text"],  # type: ignore[arg-type]
        session_id=f"golden-{name}",
        diarization_available=True,
    )

    assert result.leak_scan_passed is True, (
        f"[{name}] leak scan FAILED on golden corpus — pipeline would "
        f"raise PIILeakError in production"
    )
    assert result.masked_text == expected["masked_text"], (
        f"[{name}] masked_text drift:\n"
        f"  got:      {result.masked_text!r}\n"
        f"  expected: {expected['masked_text']!r}"
    )
    assert sorted(t.value for t in result.entity_types) == sorted(
        expected["entity_types"]
    ), (
        f"[{name}] entity_types drift:\n"
        f"  got:      {sorted(t.value for t in result.entity_types)}\n"
        f"  expected: {sorted(expected['entity_types'])}"
    )


@pytest.mark.golden
def test_golden_expected_types_cover_fixture_claims(
    pipeline: MaskingPipeline,
) -> None:
    """Each fixture's `expected_types` must match what v2 actually produces.

    This test runs independently of the golden expected file — it's a
    coherence check for the fixtures themselves.
    """
    for case in _load_fixtures():
        name = case["name"]
        text = case["text"]
        expected_types = set(case["expected_types"])  # type: ignore[arg-type]
        result = pipeline.mask(
            text=text, session_id=f"coherence-{name}", diarization_available=True
        )
        got_types = {t.value for t in result.entity_types}
        assert expected_types.issubset(got_types), (
            f"[{name}] claimed expected_types {expected_types} missing from "
            f"actual {got_types}"
        )

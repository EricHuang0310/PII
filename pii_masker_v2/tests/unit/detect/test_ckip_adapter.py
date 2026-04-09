"""Tests for the CKIP NER adapter.

Most of these run without CKIP installed — they exercise the adapter's
fail-safe paths (empty text, pre-warmup validation, error propagation).
Tests that need the real model are marked `requires_ckip` and skipped when
`ckip_transformers` isn't available.
"""
from __future__ import annotations

import importlib
from unittest.mock import MagicMock

import pytest

from pii_masker.detect.ner.ckip_adapter import CkipNerAdapter
from pii_masker.domain.entity_type import EntityType


def _ckip_available() -> bool:
    try:
        importlib.import_module("ckip_transformers")
    except ImportError:
        return False
    return True


@pytest.mark.unit
def test_ckip_adapter_empty_text_returns_empty() -> None:
    adapter = CkipNerAdapter()
    # Empty text — must NOT attempt to warm up the model
    assert adapter.detect("") == ()
    assert not adapter.is_warmed_up


@pytest.mark.unit
def test_ckip_adapter_detector_id_format() -> None:
    adapter = CkipNerAdapter(model="bert-tiny")
    assert adapter.detector_id == "ner:ckip:bert-tiny:v1"


@pytest.mark.unit
def test_ckip_adapter_entity_types_covers_person_location_org() -> None:
    adapter = CkipNerAdapter()
    assert adapter.entity_types == frozenset(
        {EntityType.PERSON, EntityType.LOCATION, EntityType.ORG}
    )


@pytest.mark.unit
def test_ckip_adapter_rejects_invalid_confidence() -> None:
    with pytest.raises(ValueError, match=r"\[0, 1\]"):
        CkipNerAdapter(confidence=1.2)


@pytest.mark.unit
def test_ckip_adapter_converts_mock_ner_output() -> None:
    """Use a MagicMock driver to test the CKIP → Detection conversion path.

    This avoids loading the real model while still exercising the full
    conversion logic (label mapping, span extraction, detector_id stamping).
    """
    adapter = CkipNerAdapter()

    # Inject a fake CKIP driver
    class FakeEntity:
        def __init__(self, word: str, ner: str, idx: tuple[int, int]) -> None:
            self.word = word
            self.ner = ner
            self.idx = idx

    fake_driver = MagicMock(
        return_value=[[
            FakeEntity("王小明", "PERSON", (2, 5)),
            FakeEntity("台北", "GPE", (7, 9)),
            FakeEntity("台積電", "ORG", (10, 13)),
            FakeEntity("something", "NUMBER", (15, 24)),  # unsupported label → dropped
        ]]
    )
    adapter._ner_driver = fake_driver  # type: ignore[attr-defined]

    dets = list(adapter.detect("我叫王小明在台北台積電上班something"))
    assert len(dets) == 3
    types = [d.entity_type for d in dets]
    assert EntityType.PERSON in types
    assert EntityType.LOCATION in types
    assert EntityType.ORG in types

    person = next(d for d in dets if d.entity_type is EntityType.PERSON)
    assert person.span.start == 2
    assert person.span.end == 5
    assert person.raw_text == "王小明"
    assert person.detector_id == "ner:ckip:bert-base:v1"


@pytest.mark.unit
def test_ckip_adapter_batch_with_mock_driver() -> None:
    adapter = CkipNerAdapter()

    class FakeEntity:
        def __init__(self, word: str, ner: str, idx: tuple[int, int]) -> None:
            self.word = word
            self.ner = ner
            self.idx = idx

    fake_driver = MagicMock(
        return_value=[
            [FakeEntity("王小明", "PERSON", (0, 3))],
            [],
            [FakeEntity("台北", "GPE", (0, 2))],
        ]
    )
    adapter._ner_driver = fake_driver  # type: ignore[attr-defined]

    batch_result = adapter.detect_batch(["王小明", "hello world", "台北"])
    assert len(batch_result) == 3
    assert len(batch_result[0]) == 1
    assert batch_result[1] == []
    assert len(batch_result[2]) == 1


@pytest.mark.unit
def test_ckip_adapter_batch_handles_empty_strings() -> None:
    """Empty strings in a batch must not be sent to the driver."""
    adapter = CkipNerAdapter()
    fake_driver = MagicMock(return_value=[[]])
    adapter._ner_driver = fake_driver  # type: ignore[attr-defined]

    batch_result = adapter.detect_batch(["", "hello", ""])
    # driver should have been called with exactly the non-empty inputs
    assert fake_driver.call_count == 1
    call_args = fake_driver.call_args[0][0]
    assert call_args == ["hello"]
    assert batch_result == [[], [], []]


@pytest.mark.skipif(_ckip_available(), reason="ckip_transformers is installed")
@pytest.mark.unit
def test_ckip_adapter_warmup_raises_helpful_error_when_missing() -> None:
    from pii_masker.domain.errors import DetectorError

    adapter = CkipNerAdapter()
    with pytest.raises(DetectorError, match="ckip-transformers is required"):
        adapter.warmup()

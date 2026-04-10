"""Tests for PseudonymTracker — including thread safety."""
from __future__ import annotations

import threading

import pytest

from pii_masker.domain.entity_type import EntityType
from pii_masker.tokenize.tracker import PseudonymTracker


@pytest.mark.unit
def test_tracker_returns_base_token_for_first_call() -> None:
    t = PseudonymTracker(session_id="S001")
    token = t.resolve(EntityType.PERSON, "王小明", "[NAME]")
    assert token == "[NAME]"


@pytest.mark.unit
def test_tracker_consistent_across_calls() -> None:
    """Same (type, original) → same token, always."""
    t = PseudonymTracker()
    a = t.resolve(EntityType.PERSON, "王小明", "[NAME]")
    b = t.resolve(EntityType.PERSON, "王小明", "[NAME]")
    assert a == b == "[NAME]"


@pytest.mark.unit
def test_tracker_different_originals_same_base_token() -> None:
    """v4 flat base tokens: every PERSON becomes [NAME] regardless of original."""
    t = PseudonymTracker()
    assert t.resolve(EntityType.PERSON, "王小明", "[NAME]") == "[NAME]"
    assert t.resolve(EntityType.PERSON, "陳美玲", "[NAME]") == "[NAME]"


@pytest.mark.unit
def test_tracker_records_all_originals_in_audit_map() -> None:
    """get_mapping() exposes every original for the audit trail."""
    t = PseudonymTracker()
    t.resolve(EntityType.PERSON, "王小明", "[NAME]")
    t.resolve(EntityType.PERSON, "陳美玲", "[NAME]")
    t.resolve(EntityType.TW_CREDIT_CARD, "4111111111111111", "[CARD]")
    mapping = t.get_mapping()
    assert mapping[EntityType.PERSON] == {"王小明": "[NAME]", "陳美玲": "[NAME]"}
    assert mapping[EntityType.TW_CREDIT_CARD] == {"4111111111111111": "[CARD]"}


@pytest.mark.unit
def test_tracker_mapping_is_read_only() -> None:
    t = PseudonymTracker()
    t.resolve(EntityType.PERSON, "x", "[NAME]")
    mapping = t.get_mapping()
    with pytest.raises(TypeError):
        mapping[EntityType.PERSON] = {}  # type: ignore[index]
    with pytest.raises(TypeError):
        mapping[EntityType.PERSON]["y"] = "[NAME]"  # type: ignore[index]


@pytest.mark.unit
def test_tracker_session_id_preserved() -> None:
    t = PseudonymTracker(session_id="S001")
    assert t.session_id == "S001"


@pytest.mark.unit
def test_tracker_thread_safe_under_concurrency() -> None:
    """Hit the tracker from many threads — no data races, no lost updates."""
    t = PseudonymTracker()
    errors: list[Exception] = []
    # Each thread inserts 50 distinct PERSON names
    THREADS = 16
    PER_THREAD = 50

    def worker(tid: int) -> None:
        try:
            for i in range(PER_THREAD):
                t.resolve(EntityType.PERSON, f"name-{tid}-{i}", "[NAME]")
        except Exception as e:
            errors.append(e)

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(THREADS)]
    for th in threads:
        th.start()
    for th in threads:
        th.join()

    assert errors == []
    mapping = t.get_mapping()
    assert len(mapping[EntityType.PERSON]) == THREADS * PER_THREAD

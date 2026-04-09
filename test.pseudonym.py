from masking.pseudonym import PseudonymTracker


def test_same_value_should_map_to_same_token():
    tracker = PseudonymTracker(session_id="s1", pseudonym_entities={"PERSON"})
    t1 = tracker.resolve("PERSON", "王小明", "[NAME]")
    t2 = tracker.resolve("PERSON", "王小明", "[NAME]")
    assert t1 == t2


def test_different_values_should_map_to_different_tokens():
    tracker = PseudonymTracker(session_id="s1", pseudonym_entities={"PERSON"})
    t1 = tracker.resolve("PERSON", "王小明", "[NAME]")
    t2 = tracker.resolve("PERSON", "陳美玲", "[NAME]")
    assert t1 != t2


def test_non_tracked_entity_returns_base_token_only():
    tracker = PseudonymTracker(session_id="s1", pseudonym_entities={"PERSON"})
    t1 = tracker.resolve("PHONE", "0912345678", "[PHONE]")
    t2 = tracker.resolve("PHONE", "0987654321", "[PHONE]")
    assert t1 == "[PHONE]"
    assert t2 == "[PHONE]"


# Issue 5 修正：第 1 個從 _1 開始，第 2 個是 _2
def test_first_value_gets_suffix_1_second_gets_suffix_2():
    tracker = PseudonymTracker(session_id="s1", pseudonym_entities={"PERSON"})
    t1 = tracker.resolve("PERSON", "王小明", "[NAME]")
    t2 = tracker.resolve("PERSON", "陳美玲", "[NAME]")
    assert t1 == "[NAME_1]"
    assert t2 == "[NAME_2]"


def test_reset_should_clear_state():
    tracker = PseudonymTracker(session_id="s1", pseudonym_entities={"PERSON"})
    tracker.resolve("PERSON", "王小明", "[NAME]")
    tracker.resolve("PERSON", "陳美玲", "[NAME]")
    tracker.reset()
    t2 = tracker.resolve("PERSON", "王小明", "[NAME]")
    # reset 後重新計數，王小明再次是第1個 → [NAME_1]
    assert t2 == "[NAME_1]"
    assert tracker.get_mapping() == {"PERSON": {"王小明": "[NAME_1]"}}


def test_get_mapping_returns_assigned_values():
    tracker = PseudonymTracker(session_id="s1", pseudonym_entities={"PERSON", "ORG"})
    tracker.resolve("PERSON", "王小明", "[NAME]")
    tracker.resolve("PERSON", "陳美玲", "[NAME]")
    tracker.resolve("ORG", "台新銀行", "[ORG]")

    mapping = tracker.get_mapping()
    assert mapping["PERSON"]["王小明"] == "[NAME_1]"
    assert mapping["PERSON"]["陳美玲"] == "[NAME_2]"
    assert mapping["ORG"]["台新銀行"] == "[ORG_1]"


def test_repr_contains_session_id():
    tracker = PseudonymTracker(session_id="call_001", pseudonym_entities={"PERSON"})
    tracker.resolve("PERSON", "王小明", "[NAME]")
    text = repr(tracker)
    assert "call_001" in text
    assert "PERSON" in text

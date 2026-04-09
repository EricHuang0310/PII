"""Tests for the policy YAML loader."""
from __future__ import annotations

from pathlib import Path

import pytest

from pii_masker.config.loader import load_policy
from pii_masker.domain.entity_type import EntityType
from pii_masker.domain.errors import PolicyError


@pytest.mark.unit
def test_loader_loads_default_policy(default_policy) -> None:  # type: ignore[no-untyped-def]
    """The packaged policy/defaults.yaml must load cleanly."""
    assert default_policy.version
    assert default_policy.schema_version == 1
    assert default_policy.score_threshold == pytest.approx(0.60)


@pytest.mark.unit
def test_loader_preserves_v3_entity_set(default_policy) -> None:  # type: ignore[no-untyped-def]
    """Every entity type in the v3/v4 TOKEN_MAP must be in the loaded token_map.

    This is our guardrail against accidental parity loss.
    """
    v3_types = set(EntityType)
    missing = v3_types - set(default_policy.token_map.keys())
    assert not missing, f"token_map missing v3/v4 types: {missing}"


@pytest.mark.unit
def test_loader_preserves_v3_priority_values(default_policy) -> None:  # type: ignore[no-untyped-def]
    """Spot-check a few ENTITY_PRIORITY values against v3/v4 config.py."""
    assert default_policy.priority_of(EntityType.TW_CREDIT_CARD) == 100
    assert default_policy.priority_of(EntityType.PERSON) == 95
    assert default_policy.priority_of(EntityType.BRANCH) == 25


@pytest.mark.unit
def test_loader_preserves_v3_risk_values(default_policy) -> None:  # type: ignore[no-untyped-def]
    """Spot-check ENTITY_RISK_LEVEL against v3/v4 config.py."""
    assert default_policy.risk_of(EntityType.TW_CREDIT_CARD) == 5
    assert default_policy.risk_of(EntityType.PERSON) == 4
    assert default_policy.risk_of(EntityType.CAMPAIGN) == 1


@pytest.mark.unit
def test_loader_preserves_v3_pseudonym_set(default_policy) -> None:  # type: ignore[no-untyped-def]
    """v3/v4 PSEUDONYM_ENTITIES set must be preserved exactly."""
    expected = {
        EntityType.PERSON, EntityType.ORG,
        EntityType.TW_CREDIT_CARD, EntityType.TW_BANK_ACCOUNT,
        EntityType.TXN_REF, EntityType.ATM_REF, EntityType.LOAN_REF,
    }
    assert default_policy.pseudonym_entities == frozenset(expected)


@pytest.mark.unit
def test_loader_compiles_all_patterns(default_policy) -> None:  # type: ignore[no-untyped-def]
    df = default_policy.diarization_fallback
    # compiled patterns should have a .pattern attribute
    assert all(hasattr(p, "pattern") for p in df.agent_question_patterns)
    assert all(hasattr(p, "pattern") for p in df.answer_patterns)
    assert len(df.agent_question_patterns) > 0
    assert len(df.answer_patterns) > 0


@pytest.mark.unit
def test_loader_preserves_v3_high_risk_txn_verbs(default_policy) -> None:  # type: ignore[no-untyped-def]
    """Every verb from v3/v4 HIGH_RISK_TXN_VERBS must be present."""
    expected = {
        "轉帳", "匯款", "扣款", "刷卡", "付款", "繳費",
        "提款", "存款", "匯入", "撥款", "退款", "退費",
        "交易", "扣繳", "扣除", "入帳", "出帳",
    }
    assert expected.issubset(set(default_policy.high_risk_txn_verbs))


@pytest.mark.unit
def test_loader_rejects_missing_file() -> None:
    with pytest.raises(PolicyError, match="Policy file not found"):
        load_policy(Path("/does/not/exist.yaml"))


@pytest.mark.unit
def test_loader_rejects_unsupported_schema_version(tmp_path: Path) -> None:
    bad = tmp_path / "bad.yaml"
    bad.write_text(
        "schema_version: 999\nversion: x\n", encoding="utf-8",
    )
    with pytest.raises(PolicyError, match="unsupported schema_version 999"):
        load_policy(bad)


@pytest.mark.unit
def test_loader_rejects_invalid_yaml(tmp_path: Path) -> None:
    bad = tmp_path / "broken.yaml"
    bad.write_text("schema_version: 1\nversion: [unterminated\n", encoding="utf-8")
    with pytest.raises(PolicyError, match="Failed to parse YAML"):
        load_policy(bad)


@pytest.mark.unit
def test_loader_rejects_missing_required_field(tmp_path: Path) -> None:
    bad = tmp_path / "missing.yaml"
    bad.write_text("schema_version: 1\n", encoding="utf-8")  # no version field etc.
    with pytest.raises(PolicyError, match="missing required field"):
        load_policy(bad)


@pytest.mark.unit
def test_loader_rejects_non_mapping_top_level(tmp_path: Path) -> None:
    bad = tmp_path / "list.yaml"
    bad.write_text("- not_a_mapping\n", encoding="utf-8")
    with pytest.raises(PolicyError, match="must be a mapping"):
        load_policy(bad)


@pytest.mark.unit
def test_loader_rejects_unknown_entity_in_priority(tmp_path: Path, policy_path: Path) -> None:
    """If someone adds an unknown entity name to entity_priority, loader must reject."""
    import yaml

    data = yaml.safe_load(policy_path.read_text(encoding="utf-8"))
    data["entity_priority"]["NOT_AN_ENTITY"] = 50
    bad = tmp_path / "bad_entity.yaml"
    bad.write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")

    with pytest.raises(PolicyError, match="Unknown entity type"):
        load_policy(bad)

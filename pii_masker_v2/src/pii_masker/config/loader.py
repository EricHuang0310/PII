"""Load policy/defaults.yaml into a frozen MaskingPolicy.

The loader is the single place where untrusted data (a YAML file) becomes a
typed domain object. Everything downstream can assume the policy is valid —
any invalid policy raises `PolicyError` here, at startup, before the pipeline
ever runs.

Validation covered:
- schema_version is present and supported
- every entity name is a valid EntityType enum member
- every regex compiles
- pseudonym_entities is a subset of entity_priority.keys()
- every numeric threshold is in range (enforced by the dataclass __post_init__)

All of this is redundant with `MaskingPolicy.__post_init__`, but having an
explicit validation layer here means YAML errors get a clear message with the
source file path, not a cryptic dataclass TypeError.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Pattern

import yaml

from pii_masker.domain.entity_type import EntityType
from pii_masker.domain.errors import PolicyError
from pii_masker.domain.policy import (
    AddressPolicy,
    ConditionalAmountPolicy,
    DiarizationFallbackPolicy,
    MaskingPolicy,
    UsabilityPolicy,
)

SUPPORTED_SCHEMA_VERSIONS: frozenset[int] = frozenset({1})

# Default policy file location — pkg-relative so tests and installed packages
# can both find it without environment variables.
_DEFAULT_POLICY_PATH: Path = (
    Path(__file__).resolve().parent.parent.parent.parent / "policy" / "defaults.yaml"
)


def _require(data: dict[str, Any], key: str, source: str) -> Any:
    if key not in data:
        raise PolicyError(f"{source}: missing required field {key!r}")
    return data[key]


def _parse_entity_set(values: list[str], source: str) -> frozenset[EntityType]:
    try:
        return frozenset(EntityType.from_str(v) for v in values)
    except ValueError as e:
        raise PolicyError(f"{source}: {e}") from e


def _parse_entity_map_int(
    values: dict[str, int], source: str
) -> dict[EntityType, int]:
    out: dict[EntityType, int] = {}
    for name, n in values.items():
        try:
            out[EntityType.from_str(name)] = int(n)
        except ValueError as e:
            raise PolicyError(f"{source}: {e}") from e
    return out


def _parse_entity_map_str(
    values: dict[str, str], source: str
) -> dict[EntityType, str]:
    out: dict[EntityType, str] = {}
    for name, token in values.items():
        try:
            out[EntityType.from_str(name)] = str(token)
        except ValueError as e:
            raise PolicyError(f"{source}: {e}") from e
    return out


def _parse_patterns(raw: list[str], source: str) -> tuple[Pattern[str], ...]:
    compiled: list[Pattern[str]] = []
    for p in raw:
        try:
            compiled.append(re.compile(p))
        except re.error as e:
            raise PolicyError(
                f"{source}: invalid regex {p!r}: {e}"
            ) from e
    return tuple(compiled)


def _parse_conditional_amount(
    raw: dict[str, Any], source: str
) -> ConditionalAmountPolicy:
    return ConditionalAmountPolicy(
        trigger_entities=_parse_entity_set(
            _require(raw, "trigger_entities", source),
            f"{source}.trigger_entities",
        ),
        proximity_chars=int(_require(raw, "proximity_chars", source)),
    )


def _parse_diarization_fallback(
    raw: dict[str, Any], source: str
) -> DiarizationFallbackPolicy:
    return DiarizationFallbackPolicy(
        answer_window_chars=int(_require(raw, "answer_window_chars", source)),
        question_boost=float(_require(raw, "question_boost", source)),
        answer_boost=float(_require(raw, "answer_boost", source)),
        diarization_threshold=float(_require(raw, "diarization_threshold", source)),
        agent_question_patterns=_parse_patterns(
            _require(raw, "agent_question_patterns", source),
            f"{source}.agent_question_patterns",
        ),
        answer_patterns=_parse_patterns(
            _require(raw, "answer_patterns", source),
            f"{source}.answer_patterns",
        ),
    )


def _parse_address(raw: dict[str, Any], source: str) -> AddressPolicy:
    return AddressPolicy(
        admin_districts=tuple(_require(raw, "admin_districts", source)),
        chain_landmarks=tuple(_require(raw, "chain_landmarks", source)),
    )


def _parse_usability(raw: dict[str, Any], source: str) -> UsabilityPolicy:
    return UsabilityPolicy(
        degraded_masking_threshold=float(
            _require(raw, "degraded_masking_threshold", source)
        ),
        asr_confidence_threshold=float(
            _require(raw, "asr_confidence_threshold", source)
        ),
    )


def load_policy(path: Path | str | None = None) -> MaskingPolicy:
    """Load and validate a MaskingPolicy from YAML.

    Args:
        path: optional path to a policy file. If None, uses the packaged
            `policy/defaults.yaml`.

    Raises:
        PolicyError: on missing fields, invalid enum names, invalid regex,
            unsupported schema version, or any dataclass validation failure.
    """
    source_path = Path(path) if path is not None else _DEFAULT_POLICY_PATH
    if not source_path.exists():
        raise PolicyError(f"Policy file not found: {source_path}")

    try:
        raw = yaml.safe_load(source_path.read_text(encoding="utf-8"))
    except yaml.YAMLError as e:
        raise PolicyError(f"Failed to parse YAML {source_path}: {e}") from e

    if not isinstance(raw, dict):
        raise PolicyError(
            f"Policy {source_path} must be a mapping at the top level, "
            f"got {type(raw).__name__}"
        )

    source = str(source_path)
    schema_version = int(_require(raw, "schema_version", source))
    if schema_version not in SUPPORTED_SCHEMA_VERSIONS:
        raise PolicyError(
            f"{source}: unsupported schema_version {schema_version} "
            f"(supported: {sorted(SUPPORTED_SCHEMA_VERSIONS)})"
        )

    try:
        return MaskingPolicy(
            version=str(_require(raw, "version", source)),
            schema_version=schema_version,
            score_threshold=float(_require(raw, "score_threshold", source)),
            mask_branch_code=bool(_require(raw, "mask_branch_code", source)),
            conditional_amount=_parse_conditional_amount(
                _require(raw, "conditional_amount", source),
                f"{source}.conditional_amount",
            ),
            high_risk_txn_verbs=tuple(
                _require(raw, "high_risk_txn_verbs", source)
            ),
            diarization_fallback=_parse_diarization_fallback(
                _require(raw, "diarization_fallback", source),
                f"{source}.diarization_fallback",
            ),
            address=_parse_address(
                _require(raw, "address", source),
                f"{source}.address",
            ),
            usability=_parse_usability(
                _require(raw, "usability", source),
                f"{source}.usability",
            ),
            entity_priority=_parse_entity_map_int(
                _require(raw, "entity_priority", source),
                f"{source}.entity_priority",
            ),
            entity_risk_level=_parse_entity_map_int(
                _require(raw, "entity_risk_level", source),
                f"{source}.entity_risk_level",
            ),
            pseudonym_entities=_parse_entity_set(
                _require(raw, "pseudonym_entities", source),
                f"{source}.pseudonym_entities",
            ),
            token_map=_parse_entity_map_str(
                _require(raw, "token_map", source),
                f"{source}.token_map",
            ),
            strict_validation=bool(raw.get("strict_validation", True)),
        )
    except (ValueError, TypeError) as e:
        raise PolicyError(f"{source}: {e}") from e

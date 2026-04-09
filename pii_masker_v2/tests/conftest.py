"""Shared fixtures for pii_masker v2 tests."""
from __future__ import annotations

from pathlib import Path

import pytest

from pii_masker.config.loader import load_policy
from pii_masker.domain.policy import MaskingPolicy

_REPO_ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="session")
def default_policy() -> MaskingPolicy:
    """The packaged policy/defaults.yaml, loaded once per test session."""
    return load_policy()


@pytest.fixture(scope="session")
def policy_path() -> Path:
    """Path to the packaged policy/defaults.yaml."""
    return _REPO_ROOT / "policy" / "defaults.yaml"

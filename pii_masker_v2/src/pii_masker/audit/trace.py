"""Trace and span ID helpers."""
from __future__ import annotations

import uuid


def new_trace_id() -> str:
    """Stable trace ID for one mask_dialogue / mask call."""
    return uuid.uuid4().hex


def new_turn_id() -> str:
    """Per-turn identifier within a dialogue."""
    return uuid.uuid4().hex[:16]

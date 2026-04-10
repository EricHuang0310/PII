"""Structured logging setup using structlog.

Optional — callers that don't have structlog installed can safely skip this
module; the rest of the pipeline does not import it.
"""
from __future__ import annotations

import logging
import sys
from typing import Any


def configure_json_logging(level: str = "INFO") -> None:
    """Configure structlog to emit JSON-formatted logs to stderr.

    Safe to call multiple times. Falls back to a no-op if structlog is
    not installed.
    """
    try:
        import structlog  # type: ignore[import-not-found]
    except ImportError:
        # No structlog — do nothing. Callers can `import logging` and log
        # in a plain format.
        return

    logging.basicConfig(
        format="%(message)s",
        stream=sys.stderr,
        level=getattr(logging, level.upper(), logging.INFO),
    )

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )


def get_logger(name: str) -> Any:
    """Return a structlog logger if available, else stdlib logging."""
    try:
        import structlog  # type: ignore[import-not-found]

        return structlog.get_logger(name)
    except ImportError:
        return logging.getLogger(name)

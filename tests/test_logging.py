"""Tests for utils.logging."""
from __future__ import annotations


def test_configure_logging_no_file() -> None:
    """configure_logging should not raise when file logging is disabled."""
    from utils.logging import configure_logging

    configure_logging(level="DEBUG", log_file=None)


def test_log_import() -> None:
    """The re-exported `log` alias must be importable and callable."""
    from utils.logging import log

    log.info("test log message — this is expected in test output")

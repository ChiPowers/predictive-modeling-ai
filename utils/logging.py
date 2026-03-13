"""Centralised logging setup using loguru."""

from __future__ import annotations

import sys
from pathlib import Path

from loguru import logger


def configure_logging(
    level: str = "INFO",
    log_file: str | Path | None = "logs/app.log",
    rotation: str = "10 MB",
    retention: str = "14 days",
    serialize: bool = False,
) -> None:
    """Configure loguru for the application.

    Call once at process startup (e.g. from main.py or a FastAPI lifespan).

    Args:
        level: Minimum log level for both stderr and file sinks.
        log_file: Path to the rotating log file. Pass None to disable file logging.
        rotation: loguru rotation policy (size or time string).
        retention: loguru retention policy.
        serialize: Emit JSON lines when True (useful for log aggregators).
    """
    logger.remove()  # remove the default handler

    fmt = (
        "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
        "<level>{level: <8}</level> | "
        "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
        "<level>{message}</level>"
    )

    logger.add(sys.stderr, level=level, format=fmt, colorize=True, serialize=serialize)

    if log_file is not None:
        logger.add(
            str(log_file),
            level=level,
            format=fmt,
            rotation=rotation,
            retention=retention,
            serialize=serialize,
            enqueue=True,  # thread-safe async writes
        )

    logger.debug("Logging configured (level={}, file={})", level, log_file)


# Re-export the configured logger so modules can do:
#   from utils.logging import log
log = logger

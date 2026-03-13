"""Tests for config.settings."""

from __future__ import annotations


def test_settings_defaults() -> None:
    """Settings must load with sensible defaults without a .env file."""
    from config.settings import settings

    assert settings.log_level == "INFO"
    assert 0 < settings.test_split < 1
    assert settings.forecast_horizon > 0
    assert settings.api_port == 8000

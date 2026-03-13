"""Test scaffold for AI narrative endpoint (POST /ai/interpret).

These tests are intentionally RED in Plan 01 — the endpoint does not exist yet.
They define expected behaviors for AI-01 through AI-05 requirements.
Tests will pass (GREEN) after Plan 02 implements the endpoint.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import anthropic
import pytest
from fastapi.testclient import TestClient

import service.api as api

# ---------------------------------------------------------------------------
# Sample data payloads
# ---------------------------------------------------------------------------
SCORE_DATA = {
    "pd": 0.34,
    "decision": "default",
    "top_factors": [{"name": "original_ltv", "value": 0.12}],
}
FORECAST_DATA = {
    "forecast": [
        {"ds": "2026-01-01", "yhat": 0.18},
        {"ds": "2026-02-01", "yhat": 0.25},
    ],
    "threshold": 0.20,
}
MONITORING_DATA = {
    "drift_features": {"feature1": {"psi": 0.25}},
    "score_drift": {"alert": True},
    "perf_drift": {"auc": 0.74},
}


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture
def mock_anthropic_client():
    """Patch service.api._get_anthropic_client with a mock that returns a canned narrative."""
    mock_message_content = MagicMock()
    mock_message_content.text = "Test narrative."

    mock_message = MagicMock()
    mock_message.content = [mock_message_content]

    mock_messages = MagicMock()
    mock_messages.create = AsyncMock(return_value=mock_message)

    mock_client = MagicMock()
    mock_client.messages = mock_messages

    with patch("service.api._get_anthropic_client", return_value=mock_client, create=True):
        yield mock_client


# ---------------------------------------------------------------------------
# Importability
# ---------------------------------------------------------------------------
def test_anthropic_importable() -> None:
    """The anthropic package is installed and importable."""
    import anthropic as _anthropic  # noqa: PLC0415

    assert hasattr(_anthropic, "AsyncAnthropic")


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------
def test_interpret_score_returns_narrative(mock_anthropic_client) -> None:
    """POST /ai/interpret with context_type='score' returns 200 with narrative string."""
    client = TestClient(api.app, raise_server_exceptions=False)
    resp = client.post(
        "/ai/interpret",
        json={"context_type": "score", "data": SCORE_DATA},
    )
    assert resp.status_code == 200
    payload = resp.json()
    assert "narrative" in payload
    assert isinstance(payload["narrative"], str)
    assert len(payload["narrative"]) > 0


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------
def test_interpret_auth_error_returns_503(monkeypatch) -> None:
    """When AsyncAnthropic raises AuthenticationError, endpoint returns 503."""
    mock_response = MagicMock()

    auth_error = anthropic.AuthenticationError(
        "Invalid API key",
        response=mock_response,
        body=None,
    )

    mock_messages = MagicMock()
    mock_messages.create = AsyncMock(side_effect=auth_error)

    mock_client = MagicMock()
    mock_client.messages = mock_messages

    monkeypatch.setattr(api, "_get_anthropic_client", lambda: mock_client, raising=False)

    client = TestClient(api.app, raise_server_exceptions=False)
    resp = client.post(
        "/ai/interpret",
        json={"context_type": "score", "data": SCORE_DATA},
    )
    assert resp.status_code == 503


def test_interpret_rate_limit_returns_429(monkeypatch) -> None:
    """When AsyncAnthropic raises RateLimitError, endpoint returns 429."""
    mock_response = MagicMock()

    rate_error = anthropic.RateLimitError(
        "Rate limit exceeded",
        response=mock_response,
        body=None,
    )

    mock_messages = MagicMock()
    mock_messages.create = AsyncMock(side_effect=rate_error)

    mock_client = MagicMock()
    mock_client.messages = mock_messages

    monkeypatch.setattr(api, "_get_anthropic_client", lambda: mock_client, raising=False)

    client = TestClient(api.app, raise_server_exceptions=False)
    resp = client.post(
        "/ai/interpret",
        json={"context_type": "score", "data": SCORE_DATA},
    )
    assert resp.status_code == 429


def test_interpret_invalid_context_type_returns_422(mock_anthropic_client) -> None:
    """POST /ai/interpret with an unknown context_type returns 422 Unprocessable Entity."""
    client = TestClient(api.app, raise_server_exceptions=False)
    resp = client.post(
        "/ai/interpret",
        json={"context_type": "invalid", "data": {}},
    )
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Prompt content assertions
# ---------------------------------------------------------------------------
def test_score_narrative_prompt_contains_pd(mock_anthropic_client) -> None:
    """The prompt sent to Claude for a score context includes the pd value as a percentage."""
    client = TestClient(api.app, raise_server_exceptions=False)
    client.post(
        "/ai/interpret",
        json={"context_type": "score", "data": SCORE_DATA},
    )

    # Retrieve the call args from the mock
    call_args = mock_anthropic_client.messages.create.call_args
    assert call_args is not None, "messages.create was not called"

    # Extract messages kwarg or positional arg
    kwargs = call_args.kwargs
    messages = kwargs.get("messages", [])
    assert len(messages) > 0, "No messages were passed to Claude"

    prompt_text = " ".join(
        m["content"] for m in messages if isinstance(m.get("content"), str)
    )
    # pd=0.34 should appear as "34%" in the prompt
    assert "34%" in prompt_text, f"Expected '34%' in prompt, got: {prompt_text!r}"


def test_forecast_narrative_prompt_contains_threshold(mock_anthropic_client) -> None:
    """The prompt sent to Claude for a forecast context includes threshold exceedance info."""
    client = TestClient(api.app, raise_server_exceptions=False)
    client.post(
        "/ai/interpret",
        json={"context_type": "forecast", "data": FORECAST_DATA},
    )

    call_args = mock_anthropic_client.messages.create.call_args
    assert call_args is not None, "messages.create was not called"

    kwargs = call_args.kwargs
    messages = kwargs.get("messages", [])
    assert len(messages) > 0, "No messages were passed to Claude"

    prompt_text = " ".join(
        m["content"] for m in messages if isinstance(m.get("content"), str)
    )
    # threshold=0.20 should appear in prompt (as "20%" or "0.20" or "0.2")
    assert any(
        token in prompt_text for token in ("20%", "0.20", "0.2", "threshold")
    ), f"Expected threshold info in prompt, got: {prompt_text!r}"


def test_monitoring_narrative_prompt_reflects_drift(mock_anthropic_client) -> None:
    """The prompt sent to Claude for a monitoring context includes drift severity info."""
    client = TestClient(api.app, raise_server_exceptions=False)
    client.post(
        "/ai/interpret",
        json={"context_type": "monitoring", "data": MONITORING_DATA},
    )

    call_args = mock_anthropic_client.messages.create.call_args
    assert call_args is not None, "messages.create was not called"

    kwargs = call_args.kwargs
    messages = kwargs.get("messages", [])
    assert len(messages) > 0, "No messages were passed to Claude"

    prompt_text = " ".join(
        m["content"] for m in messages if isinstance(m.get("content"), str)
    )
    # drift info from MONITORING_DATA: PSI 0.25, alert True, AUC 0.74
    assert any(
        token in prompt_text for token in ("drift", "psi", "PSI", "0.25", "alert")
    ), f"Expected drift info in prompt, got: {prompt_text!r}"

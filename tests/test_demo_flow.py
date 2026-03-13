"""Test scaffold for Phase 3: Demo Flow and Portfolio Dashboard.

Covers requirements DEMO-01..04 and PORT-01..03.
Structural HTML tests (7) will FAIL until Plan 02 modifies index.html.
Backend tests (2) will PASS after Task 2 adds the batch prompt branch.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from service.api import _build_prompt, app

client = TestClient(app, raise_server_exceptions=False)


# ---------------------------------------------------------------------------
# DEMO-01: Run Demo button and checklist container exist in HTML
# ---------------------------------------------------------------------------


def test_demo_button_html_structure() -> None:
    """GET / contains runDemoBtn and demoChecklist elements (DEMO-01).

    EXPECTED STATE: FAILS until Plan 02 adds these elements to index.html.
    """
    res = client.get("/")
    assert res.status_code == 200
    assert 'id="runDemoBtn"' in res.text
    assert 'id="demoChecklist"' in res.text


# ---------------------------------------------------------------------------
# DEMO-02: Job form is hidden at page load
# ---------------------------------------------------------------------------


def test_job_form_hidden() -> None:
    """GET / jobForm element has hidden attribute or is absent from visible markup (DEMO-02).

    EXPECTED STATE: FAILS until Plan 02 adds/modifies the form element.
    """
    res = client.get("/")
    assert res.status_code == 200
    # The form must not appear as a bare visible form — it should carry `hidden`
    # or not be rendered at all in the initial HTML.
    assert 'id="jobForm"' not in res.text or 'id="jobForm" class="stack" hidden' in res.text


# ---------------------------------------------------------------------------
# DEMO-03: Checklist has exactly five steps
# ---------------------------------------------------------------------------


def test_checklist_five_steps() -> None:
    """GET / contains five elements with class demo-step (DEMO-03).

    EXPECTED STATE: FAILS until Plan 02 adds five .demo-step elements.
    """
    res = client.get("/")
    assert res.status_code == 200
    assert res.text.count('class="demo-step"') == 5


# ---------------------------------------------------------------------------
# DEMO-04: Completion message element exists
# ---------------------------------------------------------------------------


def test_completion_message_element() -> None:
    """GET / contains element with id demoComplete (DEMO-04).

    EXPECTED STATE: FAILS until Plan 02 adds the demoComplete element.
    """
    res = client.get("/")
    assert res.status_code == 200
    assert 'id="demoComplete"' in res.text


# ---------------------------------------------------------------------------
# PORT-01: Portfolio table structure
# ---------------------------------------------------------------------------


def test_portfolio_table_structure() -> None:
    """GET / contains portfolioTable and does NOT contain batchView element (PORT-01).

    EXPECTED STATE: FAILS until Plan 02 restructures the HTML.
    """
    res = client.get("/")
    assert res.status_code == 200
    assert 'id="portfolioTable"' in res.text
    assert 'id="batchView"' not in res.text


# ---------------------------------------------------------------------------
# PORT-02: Portfolio donut chart element
# ---------------------------------------------------------------------------


def test_portfolio_donut_element() -> None:
    """GET / contains portfolioDonut element (PORT-02).

    EXPECTED STATE: FAILS until Plan 02 adds the portfolioDonut element.
    """
    res = client.get("/")
    assert res.status_code == 200
    assert 'id="portfolioDonut"' in res.text


# ---------------------------------------------------------------------------
# PORT-03: Batch narrative element
# ---------------------------------------------------------------------------


def test_batch_narrative_element() -> None:
    """GET / contains batchNarrative element (PORT-03).

    EXPECTED STATE: FAILS until Plan 02 adds the batchNarrative element.
    """
    res = client.get("/")
    assert res.status_code == 200
    assert 'id="batchNarrative"' in res.text


# ---------------------------------------------------------------------------
# DEMO-02 (infra): Seed demo job endpoint returns 202
# ---------------------------------------------------------------------------


def test_seed_demo_job_submits() -> None:
    """POST /jobs/seed-demo returns 202 Accepted (job infra up).

    EXPECTED STATE: PASSES if job infrastructure is running.
    Uses all-default payload (empty JSON body).
    """
    res = client.post("/jobs/seed-demo", json={})
    assert res.status_code == 202


# ---------------------------------------------------------------------------
# PORT-03 (backend): POST /ai/interpret with batch context returns narrative
# ---------------------------------------------------------------------------


def test_ai_interpret_batch_context() -> None:
    """POST /ai/interpret with context_type='batch' returns 200 with non-empty narrative (PORT-03).

    Uses the same mock pattern as test_ai_interpret.py — Claude API is not available in CI.
    EXPECTED STATE: PASSES after Task 2 adds the batch branch to _build_prompt
    and updates InterpretRequest to accept 'batch' context_type.
    """
    mock_content = MagicMock()
    mock_content.text = "Portfolio looks moderate risk. Recommend quarterly review."

    mock_message = MagicMock()
    mock_message.content = [mock_content]

    mock_messages = MagicMock()
    mock_messages.create = AsyncMock(return_value=mock_message)

    mock_client = MagicMock()
    mock_client.messages = mock_messages

    with patch("service.api._get_anthropic_client", return_value=mock_client, create=True):
        payload = {
            "context_type": "batch",
            "data": {
                "results": [
                    {"pd": 0.34, "decision": "current", "top_factors": [{"name": "orig_ltv", "value": 0.12}]},
                    {"pd": 0.72, "decision": "default", "top_factors": [{"name": "orig_dti", "value": 0.18}]},
                ],
                "count": 2,
            },
        }
        res = client.post("/ai/interpret", json=payload)
    assert res.status_code == 200
    body = res.json()
    assert "narrative" in body
    assert len(body["narrative"]) > 0


# ---------------------------------------------------------------------------
# PORT-03 (unit): _build_prompt("batch", ...) returns portfolio-specific prompt
# ---------------------------------------------------------------------------


def test_build_prompt_batch_context() -> None:
    """_build_prompt('batch', {...}) returns a string mentioning portfolio, count, and a percentage.

    EXPECTED STATE: PASSES after Task 2 adds the batch branch.
    """
    data = {
        "results": [{"pd": 0.34}, {"pd": 0.72}],
        "count": 2,
    }
    prompt = _build_prompt("batch", data)
    assert isinstance(prompt, str)
    assert "portfolio" in prompt.lower()
    # Must contain at least one digit (count or percentage figure)
    assert any(ch.isdigit() for ch in prompt)

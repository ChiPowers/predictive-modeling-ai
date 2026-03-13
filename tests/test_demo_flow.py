"""Structural HTML tests for the Phase 3 demo flow and portfolio dashboard redesign.

Covers requirements DEMO-01, DEMO-03, DEMO-04, PORT-01, PORT-02, PORT-03.
"""
from __future__ import annotations

from fastapi.testclient import TestClient

import service.api as api

client = TestClient(api.app, raise_server_exceptions=False)


def test_demo_button_html_structure() -> None:
    """GET / contains #runDemoBtn and #demoChecklist — no <ol> numbered instruction list (DEMO-01)."""
    res = client.get("/")
    assert res.status_code == 200
    assert 'id="runDemoBtn"' in res.text
    assert 'id="demoChecklist"' in res.text
    # The old numbered instruction list should be gone — no plain <ol> in the Run Demo card
    # We verify by ensuring old instruction text is absent
    assert "Submit <code>seed-demo</code> job." not in res.text


def test_job_form_hidden() -> None:
    """GET / has jobForm with hidden attribute — form exists but is not visible (DEMO-03)."""
    res = client.get("/")
    assert res.status_code == 200
    assert 'id="jobForm"' in res.text
    assert 'id="jobForm" class="stack" hidden' in res.text


def test_checklist_five_steps() -> None:
    """GET / contains exactly five .demo-step elements (DEMO-04)."""
    res = client.get("/")
    assert res.status_code == 200
    # Count occurrences of class="demo-step"
    assert res.text.count('class="demo-step"') == 5
    # Verify all steps start as pending
    assert res.text.count('data-state="pending"') >= 5


def test_completion_message_element() -> None:
    """GET / contains #demoComplete element (DEMO-04)."""
    res = client.get("/")
    assert res.status_code == 200
    assert 'id="demoComplete"' in res.text


def test_portfolio_table_structure() -> None:
    """GET / contains #portfolioTable and no #batchView (PORT-01)."""
    res = client.get("/")
    assert res.status_code == 200
    assert 'id="portfolioTable"' in res.text
    assert 'id="batchView"' not in res.text


def test_portfolio_donut_element() -> None:
    """GET / contains #portfolioDonut element (PORT-02)."""
    res = client.get("/")
    assert res.status_code == 200
    assert 'id="portfolioDonut"' in res.text


def test_batch_narrative_element() -> None:
    """GET / contains #batchNarrative element (PORT-03)."""
    res = client.get("/")
    assert res.status_code == 200
    assert 'id="batchNarrative"' in res.text

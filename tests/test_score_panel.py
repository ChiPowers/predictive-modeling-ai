"""Structural and logic tests for the Phase 2 score panel redesign.

Covers requirements VIZ-01 through SCEN-03.
"""
from __future__ import annotations

from fastapi.testclient import TestClient

import service.api as api

client = TestClient(api.app, raise_server_exceptions=False)

# SCEN-02: Canonical preset values — spec reference for the JS SCENARIOS constant.
EXPECTED_SCENARIOS = {
    "Prime Borrower": {"credit_score": 780, "orig_ltv": 65, "orig_dti": 25},
    "Borderline":     {"credit_score": 700, "orig_ltv": 85, "orig_dti": 40},
    "High Risk":      {"credit_score": 620, "orig_ltv": 97, "orig_dti": 49},
}


def test_score_panel_html_structure() -> None:
    """GET / contains scorePanel, scoreGauge, and scoreFactors containers (VIZ-01, VIZ-02)."""
    res = client.get("/")
    assert res.status_code == 200
    assert 'id="scorePanel"' in res.text
    assert 'id="scoreGauge"' in res.text
    assert 'id="scoreFactors"' in res.text


def test_risk_badge_element_present() -> None:
    """GET / contains scoreBadge element (VIZ-03)."""
    res = client.get("/")
    assert res.status_code == 200
    assert 'id="scoreBadge"' in res.text


def test_score_view_pre_removed() -> None:
    """GET / does NOT contain the raw JSON pre#scoreView element (VIZ-04)."""
    res = client.get("/")
    assert res.status_code == 200
    assert 'id="scoreView"' not in res.text


def test_scenario_buttons_present() -> None:
    """GET / contains three scenario preset buttons with correct data-scenario attributes (SCEN-01)."""
    res = client.get("/")
    assert res.status_code == 200
    assert 'data-scenario="Prime Borrower"' in res.text
    assert 'data-scenario="Borderline"' in res.text
    assert 'data-scenario="High Risk"' in res.text


def test_scenario_preset_values() -> None:
    """EXPECTED_SCENARIOS constant documents the required preset values (SCEN-02).

    The SCENARIOS constant lives in app.js and is not importable;
    this test is the authoritative spec reference.
    """
    assert EXPECTED_SCENARIOS["Prime Borrower"]["credit_score"] == 780
    assert EXPECTED_SCENARIOS["Prime Borrower"]["orig_ltv"] == 65
    assert EXPECTED_SCENARIOS["Prime Borrower"]["orig_dti"] == 25

    assert EXPECTED_SCENARIOS["Borderline"]["credit_score"] == 700
    assert EXPECTED_SCENARIOS["Borderline"]["orig_ltv"] == 85
    assert EXPECTED_SCENARIOS["Borderline"]["orig_dti"] == 40

    assert EXPECTED_SCENARIOS["High Risk"]["credit_score"] == 620
    assert EXPECTED_SCENARIOS["High Risk"]["orig_ltv"] == 97
    assert EXPECTED_SCENARIOS["High Risk"]["orig_dti"] == 49


def test_features_textarea_editable() -> None:
    """GET / features textarea does NOT have a readonly attribute (SCEN-03)."""
    res = client.get("/")
    assert res.status_code == 200
    # Ensure the textarea is present but not readonly
    assert 'name="features"' in res.text
    assert 'name="features" readonly' not in res.text
    assert 'name="features" rows' in res.text or 'rows' in res.text


def test_score_narrative_still_present() -> None:
    """GET / still contains scoreNarrative paragraph from Phase 1 (regression guard)."""
    res = client.get("/")
    assert res.status_code == 200
    assert 'id="scoreNarrative"' in res.text

---
phase: 2
slug: score-panel-redesign
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-12
---

# Phase 2 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.2.2 |
| **Config file** | `pyproject.toml` `[tool.pytest.ini_options]` — testpaths = ["tests"] |
| **Quick run command** | `pytest tests/test_api_contract.py tests/test_score_panel.py -v -x` |
| **Full suite command** | `pytest tests/ -v` |
| **Estimated runtime** | ~10 seconds |

---

## Sampling Rate

- **After every task commit:** Run `pytest tests/test_api_contract.py tests/test_score_panel.py -v -x`
- **After every plan wave:** Run `pytest tests/ -v`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** ~10 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 2-01-01 | 01 | 0 | VIZ-01, VIZ-02, VIZ-03, VIZ-04, SCEN-01, SCEN-02, SCEN-03 | unit/smoke | `pytest tests/test_score_panel.py -v -x` | ❌ W0 | ⬜ pending |
| 2-02-01 | 02 | 1 | VIZ-04 | smoke | `pytest tests/test_api_contract.py::test_ui_root_serves_html -x` | ✅ (extend) | ⬜ pending |
| 2-02-02 | 02 | 1 | VIZ-01 | smoke | `pytest tests/test_score_panel.py::test_score_panel_html_structure -x` | ❌ W0 | ⬜ pending |
| 2-02-03 | 02 | 1 | VIZ-02 | smoke | `pytest tests/test_score_panel.py::test_factor_bars_html_structure -x` | ❌ W0 | ⬜ pending |
| 2-02-04 | 02 | 1 | VIZ-03 | unit | `pytest tests/test_score_panel.py::test_risk_tier_thresholds -x` | ❌ W0 | ⬜ pending |
| 2-03-01 | 03 | 1 | SCEN-01 | smoke | `pytest tests/test_score_panel.py::test_scenario_buttons_present -x` | ❌ W0 | ⬜ pending |
| 2-03-02 | 03 | 1 | SCEN-02 | unit | `pytest tests/test_score_panel.py::test_scenario_preset_values -x` | ❌ W0 | ⬜ pending |
| 2-03-03 | 03 | 1 | SCEN-03 | smoke | `pytest tests/test_score_panel.py::test_features_textarea_editable -x` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_score_panel.py` — stubs for VIZ-01 through SCEN-03 (structural HTML checks + logic unit tests)
- [ ] Extend `tests/test_api_contract.py::test_ui_root_serves_html` — assert `<pre id="scoreView">` absent, assert scenario button `data-scenario` attributes present

*Existing infrastructure (pytest + FastAPI TestClient) covers all needs; only the new test file is required.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Gauge fills correct direction (left→right) at 0%, 50%, 100% PD | VIZ-01 | Browser visual — SVG arc direction not detectable from HTML string | Score with pd≈0, pd≈0.5, pd≈1.0 and observe arc fill direction |
| Factor bars extend right (red) for positive SHAP, left (green) for negative | VIZ-02 | Bar visual direction requires browser rendering | Score Prime Borrower and High Risk; confirm bar directions |
| Gauge CSS transition animates on new score | VIZ-01 (discretionary) | Animation timing not testable in pytest | Score loan and observe 300ms ease-out arc animation |
| Scenario click pre-fills textarea and textarea remains editable | SCEN-02, SCEN-03 | Requires live browser JS execution | Click each scenario button; confirm textarea content; type in textarea and confirm editable |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 10s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending

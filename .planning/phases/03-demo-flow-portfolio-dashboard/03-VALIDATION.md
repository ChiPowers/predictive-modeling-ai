---
phase: 3
slug: demo-flow-portfolio-dashboard
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-12
---

# Phase 3 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (via pyproject.toml `[tool.pytest.ini_options]`) |
| **Config file** | `pyproject.toml` — `testpaths = ["tests"]`, `addopts = "-v"` |
| **Quick run command** | `pytest tests/test_demo_flow.py -x -q` |
| **Full suite command** | `pytest tests/ -x -q` |
| **Estimated runtime** | ~10 seconds |

---

## Sampling Rate

- **After every task commit:** Run `pytest tests/test_demo_flow.py -x -q`
- **After every plan wave:** Run `pytest tests/ -x -q`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 10 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 3-W0-01 | W0 | 0 | DEMO-01 | structural/HTML | `pytest tests/test_demo_flow.py::test_demo_button_html_structure -x` | ❌ W0 | ⬜ pending |
| 3-W0-02 | W0 | 0 | DEMO-01 | structural/HTML | `pytest tests/test_demo_flow.py::test_job_form_hidden -x` | ❌ W0 | ⬜ pending |
| 3-W0-03 | W0 | 0 | DEMO-02 | integration | `pytest tests/test_demo_flow.py::test_seed_demo_job_submits -x` | ❌ W0 | ⬜ pending |
| 3-W0-04 | W0 | 0 | DEMO-03 | structural/HTML | `pytest tests/test_demo_flow.py::test_checklist_five_steps -x` | ❌ W0 | ⬜ pending |
| 3-W0-05 | W0 | 0 | DEMO-04 | structural/HTML | `pytest tests/test_demo_flow.py::test_completion_message_element -x` | ❌ W0 | ⬜ pending |
| 3-W0-06 | W0 | 0 | PORT-01 | structural/HTML | `pytest tests/test_demo_flow.py::test_portfolio_table_structure -x` | ❌ W0 | ⬜ pending |
| 3-W0-07 | W0 | 0 | PORT-02 | structural/HTML | `pytest tests/test_demo_flow.py::test_portfolio_donut_element -x` | ❌ W0 | ⬜ pending |
| 3-W0-08 | W0 | 0 | PORT-03 | structural + unit | `pytest tests/test_demo_flow.py::test_batch_narrative_element tests/test_demo_flow.py::test_ai_interpret_batch_context -x` | ❌ W0 | ⬜ pending |
| 3-W0-09 | W0 | 0 | PORT-03 | unit | `pytest tests/test_demo_flow.py::test_build_prompt_batch_context -x` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_demo_flow.py` — stubs for DEMO-01, DEMO-02, DEMO-03, DEMO-04, PORT-01, PORT-02, PORT-03
- [ ] No framework config gap — pytest already configured in pyproject.toml

*Existing infrastructure (pytest + TestClient pattern) covers all phase requirements.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Checklist step animation (spinner → checkmark transitions) | DEMO-01 | CSS animation/JS timing cannot be reliably tested headlessly | Run demo in browser; verify spinner shows on current step, check fills on completion |
| Auto-scroll to Portfolio section after demo completes | DEMO-04 | Browser scroll behavior not testable in pytest | Complete demo run; verify viewport scrolls to portfolio table |
| Donut chart SVG renders correctly with mixed tier data | PORT-02 | SVG visual rendering requires browser | Load batch results with loans across multiple tiers; verify colored segments appear |
| "Restart from beginning" button shown on step failure | DEMO-01 | Error flow requires live job failure | Manually trigger a job failure; verify button appears and resets checklist |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 15s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending

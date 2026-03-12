---
phase: 1
slug: ai-narrative-backend
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-12
---

# Phase 1 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.2.2 |
| **Config file** | `pyproject.toml` `[tool.pytest.ini_options]` |
| **Quick run command** | `pytest tests/test_ai_interpret.py -x -v` |
| **Full suite command** | `pytest tests/ -v` |
| **Estimated runtime** | ~10 seconds |

---

## Sampling Rate

- **After every task commit:** Run `pytest tests/test_ai_interpret.py -x -v`
- **After every plan wave:** Run `pytest tests/ -v`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 10 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 1-01-01 | 01 | 0 | AI-05 | smoke | `pytest tests/test_ai_interpret.py::test_anthropic_importable -x` | ❌ W0 | ⬜ pending |
| 1-01-02 | 01 | 0 | AI-04 | unit | `pytest tests/test_ai_interpret.py::test_interpret_score_returns_narrative -x` | ❌ W0 | ⬜ pending |
| 1-01-03 | 01 | 0 | AI-04 | unit | `pytest tests/test_ai_interpret.py::test_interpret_auth_error_returns_503 -x` | ❌ W0 | ⬜ pending |
| 1-01-04 | 01 | 0 | AI-04 | unit | `pytest tests/test_ai_interpret.py::test_interpret_rate_limit_returns_429 -x` | ❌ W0 | ⬜ pending |
| 1-01-05 | 01 | 0 | AI-04 | unit | `pytest tests/test_ai_interpret.py::test_interpret_invalid_context_type_returns_422 -x` | ❌ W0 | ⬜ pending |
| 1-01-06 | 01 | 1 | AI-01 | smoke | `pytest tests/test_ai_interpret.py::test_score_narrative_prompt_contains_pd -x` | ❌ W0 | ⬜ pending |
| 1-01-07 | 01 | 1 | AI-02 | unit | `pytest tests/test_ai_interpret.py::test_forecast_narrative_prompt_contains_threshold -x` | ❌ W0 | ⬜ pending |
| 1-01-08 | 01 | 1 | AI-03 | unit | `pytest tests/test_ai_interpret.py::test_monitoring_narrative_prompt_reflects_drift -x` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_ai_interpret.py` — stubs for AI-01 through AI-05 (does not exist yet)
- [ ] Mock `AsyncAnthropic` client fixture returning stub narrative — add as local fixture in `tests/test_ai_interpret.py`
- [ ] `anthropic>=0.84` installable: verify `pip install "anthropic>=0.84"` succeeds in CI environment

*All tests mock `AsyncAnthropic.messages.create` — no real API calls in test suite. Use `unittest.mock.AsyncMock` or `pytest-mock`.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Narrative paragraph appears below score result in browser | AI-01 | Requires browser + real ANTHROPIC_API_KEY | 1. Set ANTHROPIC_API_KEY. 2. Score a loan. 3. Verify narrative paragraph appears below score result. |
| Narrative paragraph appears below forecast result in browser | AI-02 | Requires browser + real API key | 1. Run a forecast. 2. Verify narrative paragraph appears below forecast output. |
| Narrative paragraph appears below monitoring result in browser | AI-03 | Requires browser + real API key | 1. Load monitoring data (available: true). 2. Verify narrative paragraph appears below monitoring summary. |
| ANTHROPIC_API_KEY never sent to browser | AI-04 | Requires network inspection | Open DevTools Network tab, score a loan, confirm no request contains the API key. |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 10s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending

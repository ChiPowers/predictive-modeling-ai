---
phase: 4
slug: monitoring-panel
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-13
---

# Phase 4 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (existing) |
| **Config file** | `pyproject.toml` |
| **Quick run command** | `pytest tests/test_api_contract.py -x -q` |
| **Full suite command** | `pytest tests/ -x -q` |
| **Estimated runtime** | ~5 seconds |

---

## Sampling Rate

- **After every task commit:** Run `pytest tests/test_api_contract.py -x -q`
- **After every plan wave:** Run `pytest tests/ -x -q`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** ~5 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 4-01-01 | 01 | 1 | MON-01 | contract | `pytest tests/test_api_contract.py::test_monitoring_summary_loads_reports -x` | ✅ | ⬜ pending |
| 4-01-02 | 01 | 1 | MON-01 | contract | `pytest tests/test_api_contract.py::test_monitoring_summary_unavailable -x` | ✅ | ⬜ pending |
| 4-01-03 | 01 | 1 | MON-02 | manual | Visual: per-feature drift badges render green/yellow/red | N/A — manual | ⬜ pending |
| 4-01-04 | 01 | 1 | MON-03 | manual | Visual: AUC row shows "Not yet available" when perf_drift is null | N/A — manual | ⬜ pending |
| 4-01-05 | 01 | 1 | MON-04 | manual | Visual: monitoringNarrative shows text (requires ANTHROPIC_API_KEY) | N/A — manual | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

None — existing infrastructure covers all phase requirements.

*Existing `pytest` infrastructure covers backend API contract; frontend rendering is human-verified. No JS test runner in project.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| `getDriftClass()` returns correct CSS class for PSI ranges | MON-02 | Vanilla JS has no test harness | Load monitoring section; verify green badge for PSI<0.1, yellow for 0.1–0.2, red for >0.2 |
| Drift badges render for each feature in `drift_features` | MON-02 | Frontend rendering, no JS runner | Load monitoring; confirm each feature row has colored badge |
| AUC row shows "Not yet available" when `perf_drift` is null | MON-03 | Frontend null-guard, no JS runner | Run demo; confirm AUC row doesn't crash and shows fallback text |
| AUC value and trend badge visible when data is present | MON-03 | Frontend rendering, no JS runner | If perf_drift data available, confirm value + trend indicator visible |
| `monitoringNarrative` shows AI text | MON-04 | Requires live ANTHROPIC_API_KEY | Load monitoring with API key set; confirm narrative paragraph appears |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 5s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending

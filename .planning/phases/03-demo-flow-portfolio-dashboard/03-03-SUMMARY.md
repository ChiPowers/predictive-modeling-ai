---
phase: 03-demo-flow-portfolio-dashboard
plan: 03
subsystem: ui
tags: [javascript, demo-flow, job-polling, orchestration, vanilla-js]

# Dependency graph
requires:
  - phase: 03-demo-flow-portfolio-dashboard
    plan: 02
    provides: "DOM skeleton — #runDemoBtn, #demoChecklist li.demo-step, #demoComplete, #portfolioTable"
  - phase: 03-demo-flow-portfolio-dashboard
    plan: 01
    provides: "HTML structure with demo section and portfolio section"
provides:
  - "runFullDemo() 5-step orchestration: seed-demo, pipeline, activate, score, forecast"
  - "pollJobById() with 3s interval and 120s timeout using succeeded/failed terminal statuses"
  - "setStepState() driving CSS state machine via data-state attribute"
  - "showDemoError() with collapsible traceback details and Restart button"
  - "startDemo() reset-and-run wrapper; initDemoButton() click handler wiring"
affects:
  - "Any phase rendering score panel or forecast chart in demo context"

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Job polling: POST /jobs/{type} → capture id → poll GET /jobs/{id} until succeeded/failed"
    - "Silent retry: 2-attempt loop, first failure continues silently, second throws"
    - "State machine via data-state: pending → active → done | failed"
    - "Async narrative: fire-and-forget .then() so primary result displays immediately"
    - "requestAnimationFrame for auto-scroll after DOM update"

key-files:
  created: []
  modified:
    - service/static/app.js

key-decisions:
  - "runFullDemo() uses SCENARIOS['Prime Borrower'] for score step — fixed scenario for repeatable demo"
  - "Model activation uses sklearn-rf (not sklearn-logreg) for demo flow — plan spec"
  - "Forecast horizon is 24 for demo run — consistent with plan spec"
  - "bootstrap() calls initDemoButton() as its first line — ensures demo wiring before other init"

patterns-established:
  - "Demo orchestration: each step wrapped in try/catch; on error calls showDemoError() and returns early"
  - "showDemoError(): injects #demoErrorSummary div after #demoChecklist with <details> traceback"

requirements-completed: [DEMO-01, DEMO-02, DEMO-03, DEMO-04]

# Metrics
duration: 7min
completed: 2026-03-13
---

# Phase 3 Plan 03: runFullDemo() Orchestration Summary

**5-step demo orchestration in vanilla JS: button click auto-executes seed, pipeline, activate, score, and forecast with animated checklist state, error recovery, and auto-scroll to portfolio**

## Performance

- **Duration:** 7 min
- **Started:** 2026-03-13T03:09:25Z
- **Completed:** 2026-03-13T03:16:00Z
- **Tasks:** 2
- **Files modified:** 1

## Accomplishments

- Implemented `setStepState()`, `pollJobById()`, `submitJobWithRetry()`, and `showDemoError()` helper functions in app.js
- Implemented `runFullDemo()` 5-step orchestration sequence with silent retry, inline error display, and auto-scroll completion
- Wired `initDemoButton()` into `bootstrap()` as first call; all 10 demo flow tests pass

## Task Commits

Each task was committed atomically:

1. **Task 1: setStepState, pollJobById, submitJobWithRetry, showDemoError helpers** - `07be2bf` (feat)
2. **Task 2: runFullDemo(), startDemo(), initDemoButton() orchestration** - `b203567` (feat)

## Files Created/Modified

- `service/static/app.js` - Added 211 lines: 4 helper functions (Task 1) + 3 orchestration functions + bootstrap update (Task 2)

## Decisions Made

- `runFullDemo()` uses the `SCENARIOS['Prime Borrower']` fixture for the score step — provides a fixed, repeatable demo scenario
- Model activation targets `sklearn-rf` (not `sklearn-logreg`) as specified in plan
- Forecast horizon is 24 months for demo run, matching plan spec
- `bootstrap()` calls `initDemoButton()` first so demo button is always wired before other form handlers run

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

- Pre-existing `test_forecast_missing_model_returns_503` failure in full suite — documented in STATE.md as out-of-scope (prophet artifact exists locally, no fix needed)

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Demo orchestration complete; clicking "Run Full Demo" drives all 5 steps end-to-end
- Portfolio rendering (batchView → #portfolioTable, #portfolioDonut, #batchNarrative) is the remaining open item from Phase 3
- Score panel and forecast chart render correctly via `renderScorePanel()` and `renderForecastChart()` called from demo flow

---
*Phase: 03-demo-flow-portfolio-dashboard*
*Completed: 2026-03-13*

---
phase: 03-demo-flow-portfolio-dashboard
plan: "02"
subsystem: ui
tags: [html, css, demo-flow, portfolio, checklist, vanilla-js-dom]

requires:
  - phase: 02-score-panel-redesign
    provides: CSS custom properties (--success, --warning, --danger, --accent, --line), .badge patterns, card structure

provides:
  - DOM skeleton for demo checklist: #demoCard, #runDemoBtn, #demoChecklist, 5x .demo-step[data-state], #demoComplete
  - Portfolio section in Batch Score card: #portfolioTable, #portfolioDonut, #batchNarrative
  - Hidden #jobForm preserved for JS reuse by runFullDemo()
  - CSS state machine for .demo-step (pending/active/done/failed) with animated .step-icon
  - #portfolioTable table/th/td sort-indicator styles
  - #portfolioDonut container styles

affects:
  - 03-03 (JS demo orchestrator targeting these element IDs)
  - 03-04 (portfolio table and donut chart JS targeting #portfolioTable, #portfolioDonut, #batchNarrative)

tech-stack:
  added: []
  patterns:
    - "data-state attribute on .demo-step drives CSS visual state via attribute selectors"
    - "step-icon pseudo-element encodes checkmark (done) and x-mark (failed) purely in CSS"
    - "@keyframes spin reuses existing animation pattern from styles.css"

key-files:
  created:
    - tests/test_demo_flow.py
  modified:
    - service/static/index.html
    - service/static/styles.css

key-decisions:
  - "demo-step state machine uses data-state attribute (not classes) so JS can update a single attribute to drive all visual transitions"
  - "jobForm hidden attribute added (not removed) — app.js initJobsForm() and runFullDemo() JS still reference it"
  - "batchView pre replaced with three semantic containers (#portfolioTable, #portfolioDonut, #batchNarrative) to support separate rendering concerns"

patterns-established:
  - "State machine pattern: data-state attribute + CSS attribute selectors for stepwise UI feedback"
  - "DOM contract pattern: HTML plan creates element IDs and data attributes; JS plans consume them without HTML changes"

requirements-completed: [DEMO-01, DEMO-03, DEMO-04, PORT-01, PORT-02, PORT-03]

duration: 15min
completed: 2026-03-12
---

# Phase 3 Plan 02: Demo Flow + Portfolio Dashboard DOM Skeleton Summary

**HTML restructure replacing static Run Demo instructions with interactive demo checklist skeleton and portfolio table/donut containers, with full CSS state machine for step progress visualization**

## Performance

- **Duration:** ~15 min
- **Started:** 2026-03-12T00:00:00Z
- **Completed:** 2026-03-13T02:42:32Z
- **Tasks:** 2
- **Files modified:** 3 (index.html, styles.css, tests/test_demo_flow.py created)

## Accomplishments
- Replaced static numbered instructions in Run Demo card with interactive #runDemoBtn + 5-step #demoChecklist DOM structure
- Added #demoComplete completion message, hidden #jobForm preserved for JS reuse
- Replaced #batchView with #portfolioTable, #portfolioDonut, #batchNarrative portfolio section
- Appended full CSS state machine: .demo-step[data-state] rules for pending/active/done/failed with animated .step-icon
- Added #portfolioTable sortable header styles with aria-sort indicators and #portfolioDonut container
- Created tests/test_demo_flow.py with 7 structural HTML tests — all pass green

## Task Commits

Each task was committed atomically:

1. **Task 1: Restructure Run Demo card and Batch Score section in index.html** - `b47dfbb` (feat)
2. **Task 2: Add CSS for demo checklist step states and portfolio section** - `2bb09c3` (feat)

## Files Created/Modified
- `service/static/index.html` - Run Demo card replaced with checklist DOM; jobForm hidden; batchView replaced with portfolio containers
- `service/static/styles.css` - Demo checklist, step-icon, @keyframes spin, portfolio table, donut container styles appended
- `tests/test_demo_flow.py` - 7 structural HTML tests covering DEMO-01, DEMO-03, DEMO-04, PORT-01, PORT-02, PORT-03

## Decisions Made
- Used `data-state` attribute (not classes) on `.demo-step` elements so JS needs one attribute update to drive all CSS transitions
- Added `hidden` attribute to `#jobForm` rather than removing it — `app.js initJobsForm()` and the planned `runFullDemo()` both need the form's submit mechanism
- Split batch score output into three semantic containers rather than one `<pre>` to allow independent rendering of table, chart, and narrative

## Deviations from Plan

None - plan executed exactly as written. The test file `tests/test_demo_flow.py` was created as part of Task 1 verification (the plan's `<verify>` block references it); this was anticipated by the plan.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- All element IDs, data attributes, and CSS classes that Plans 03 and 04 will target are now in place
- DOM contract is established: #runDemoBtn, #demoChecklist, .demo-step[data-state], #demoComplete, #portfolioTable, #portfolioDonut, #batchNarrative
- Plan 03 (JS demo orchestrator) and Plan 04 (portfolio table/donut JS) can proceed immediately

---
*Phase: 03-demo-flow-portfolio-dashboard*
*Completed: 2026-03-12*

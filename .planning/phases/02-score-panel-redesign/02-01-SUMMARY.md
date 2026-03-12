---
phase: 02-score-panel-redesign
plan: 01
subsystem: ui
tags: [html, css, pytest, tdd, score-panel, fastapi]

# Dependency graph
requires:
  - phase: 01-ai-narrative-backend
    provides: scoreNarrative paragraph in index.html used as regression guard
provides:
  - tests/test_score_panel.py with 7 assertions covering VIZ-01..SCEN-03
  - index.html score panel DOM containers (scorePanel, scoreGauge, scoreBadge, scoreFactors)
  - styles.css risk color tokens (--success, --warning) and component CSS classes
affects: [02-score-panel-redesign plan 02 (JS implementation builds against these DOM containers)]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - TDD scaffold written before DOM changes — structural tests start in RED, go GREEN after HTML update
    - EXPECTED_SCENARIOS Python dict as authoritative spec reference for JS constant (not importable)
    - Buttons inside form use type="button" to prevent accidental form submission

key-files:
  created:
    - tests/test_score_panel.py
  modified:
    - service/static/index.html
    - service/static/styles.css
    - tests/test_api_contract.py

key-decisions:
  - "scoreView pre removed completely per locked VIZ-04 decision — no collapse/toggle"
  - "Scenario buttons placed before Threshold label inside scoreForm so tab order is intuitive"
  - "scorePanel hidden attribute set — JS implementation (Plan 02) reveals it on first score result"
  - "EXPECTED_SCENARIOS Python dict serves as spec reference since JS SCENARIOS constant is not importable"

patterns-established:
  - "Score panel structural tests use GET / + assert against res.text — matches existing test_api_contract.py pattern"
  - "Scenario buttons always use type=button inside forms — prevents default form submission"

requirements-completed: [VIZ-01, VIZ-02, VIZ-03, VIZ-04, SCEN-01, SCEN-02, SCEN-03]

# Metrics
duration: 19min
completed: 2026-03-12
---

# Phase 2 Plan 01: Test Scaffold and HTML/CSS Foundation Summary

**TDD scaffold with 7 score panel tests (RED-to-GREEN), DOM containers for gauge/badge/factors, and risk color tokens in CSS**

## Performance

- **Duration:** ~19 min
- **Started:** 2026-03-12T22:06:03Z
- **Completed:** 2026-03-12T22:24:42Z
- **Tasks:** 3
- **Files modified:** 4

## Accomplishments

- Created `tests/test_score_panel.py` with 7 test functions covering all 7 Phase 2 requirements — confirmed RED state before HTML changes, GREEN state after
- Updated `service/static/index.html`: removed `pre#scoreView`, added `div#scorePanel` with gauge/badge/factors containers, added three scenario preset buttons inside the score form
- Updated `service/static/styles.css`: added `--success` and `--warning` CSS custom properties, badge color variants, factor bar classes, and scenario button styles
- Extended `test_ui_root_serves_html` in `test_api_contract.py` with scoreView absence assertion

## Task Commits

Each task was committed atomically:

1. **Task 1: Create test scaffold for Phase 2 structural requirements** — `276c873` (test)
2. **Task 2: Add risk CSS tokens and visual component styles to styles.css** — `02c1dcf` (feat)
3. **Task 3: Update index.html — remove scoreView pre, add score panel containers and scenario buttons** — `2d7c391` (feat)

**Plan metadata:** (docs commit follows)

_Note: Task 1 is TDD — tests written in RED state first, then Tasks 2+3 bring them to GREEN._

## Files Created/Modified

- `tests/test_score_panel.py` — 7 test functions covering VIZ-01..VIZ-04 and SCEN-01..SCEN-03 with EXPECTED_SCENARIOS constant
- `tests/test_api_contract.py` — Extended test_ui_root_serves_html with scoreView absence assertion
- `service/static/index.html` — Removed pre#scoreView; added div#scorePanel (hidden) with scoreGauge, scoreBadge, scoreFactors; added three scenario buttons with type="button"
- `service/static/styles.css` — Added --success, --warning to :root; badge color variants; score panel, factor bar, and scenario button styles

## Decisions Made

- `scoreView` pre removed completely per locked VIZ-04 decision — no collapse/toggle option was presented
- `scorePanel` starts with `hidden` attribute; JS implementation (Plan 02) will remove it on first score
- Scenario buttons placed at top of form (before Threshold field) for natural tab order
- `EXPECTED_SCENARIOS` Python dict acts as canonical spec reference since JS `SCENARIOS` constant is not importable from Python tests

## Deviations from Plan

None — plan executed exactly as written.

## Issues Encountered

One pre-existing test failure exists in the suite (`test_service_smoke.py::test_forecast_missing_model_returns_503` returning 200 instead of 503) — not introduced or affected by this plan's changes. Out of scope per deviation scope boundary.

## Next Phase Readiness

- DOM containers are in place; JS implementation (Plan 02) can query `#scorePanel`, `#scoreGauge`, `#scoreBadge`, `#scoreFactors` directly
- CSS classes `.badge-success`, `.badge-warning`, `.badge-danger`, `.factor-bar--left`, `.factor-bar--right`, `.btn-scenario` are defined and ready to apply
- Test suite provides regression coverage for all 7 Phase 2 requirements

---
*Phase: 02-score-panel-redesign*
*Completed: 2026-03-12*

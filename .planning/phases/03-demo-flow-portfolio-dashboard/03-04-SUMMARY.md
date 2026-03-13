---
phase: 03-demo-flow-portfolio-dashboard
plan: "04"
subsystem: frontend
tags: [portfolio-dashboard, batch-scoring, svg-chart, sortable-table, vanilla-js]
dependency_graph:
  requires: [03-03, 03-02]
  provides: [renderPortfolioTable, renderDonutChart, portfolio-dashboard-ui]
  affects: [service/static/app.js]
tech_stack:
  added: []
  patterns: [SVG arc math, module-level sort state, donut chart with degenerate fallback]
key_files:
  created: []
  modified:
    - service/static/app.js
decisions:
  - portfolioSort is module-level (not function-scoped) so sort state persists across re-renders triggered by column header clicks
  - Degenerate single-tier case uses SVG <circle> not arc path to avoid 360-degree arc math edge case
  - Tier colors use inline hex fills in SVG (not CSS custom properties) for cross-browser SVG fill compatibility
  - initBatchForm error path writes to #portfolioTable directly (not setOutput) since batchView pre was removed in Plan 02
metrics:
  duration_minutes: 3
  completed_date: "2026-03-13"
  tasks_completed: 2
  files_modified: 1
---

# Phase 03 Plan 04: Portfolio Dashboard — Table, Donut Chart, Narrative Summary

**One-liner:** Replaced raw JSON batch output with sortable portfolio table, SVG donut risk-tier chart, and AI narrative using inline SVG arc math and module-level sort state.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Implement renderPortfolioTable() with module-level sort state | 6253cab | service/static/app.js |
| 2 | Implement renderDonutChart(), update initBatchForm(), verify suite | 6307daa | service/static/app.js |

## What Was Built

**renderPortfolioTable(results)** renders a four-column table (Loan #, PD Score %, Risk Tier badge, Top Risk Factor) into `#portfolioTable`. Column headers are clickable — clicking a header sorts by that column ascending; clicking again reverses to descending. Sort state is held in the module-level `portfolioSort` object so re-renders triggered by clicks retain the chosen column.

**polarToCartesian() / arcPath()** are SVG math helpers that convert angle + radius to cartesian coordinates and produce SVG path arc strings for the donut chart segments.

**renderDonutChart(results)** renders an SVG donut chart into `#portfolioDonut` showing the count of loans per risk tier (Low, Moderate, High, Very High). When all loans belong to a single tier, a `<circle>` element is used instead of an arc path to avoid the degenerate 360-degree arc edge case. Tier colors are inline hex values (`#1a7f37`, `#9a6700`, `#d97706`, `#b42318`) because CSS custom properties do not resolve in SVG `fill` attributes in all browsers.

**initBatchForm() updated** — the submit handler now calls `renderPortfolioTable`, `renderDonutChart`, and `fetchNarrative("batch", ...)` instead of `setOutput("batchView", ...)`. Sort state is reset to `{ col: 'pd', dir: 'desc' }` on each new batch result. Error path writes directly to `#portfolioTable` (the `batchView` pre element was removed in Plan 02).

## Verification Results

- `grep "batchView" service/static/app.js` — returns nothing (removed)
- `grep "renderPortfolioTable"` — appears in `initBatchForm()` and function definition
- `grep "fetchNarrative.*batch"` — confirms batch narrative wired
- `grep "succeeded"` — only in `pollJobById` demo flow, no contamination
- `pytest tests/ -q` — 160 passed, 1 skipped, 1 pre-existing prophet failure (unrelated to this plan, documented in Phase 02)

## Deviations from Plan

None — plan executed exactly as written.

## Self-Check

Files exist:
- service/static/app.js: modified in place

Commits exist:
- 6253cab: Task 1 — renderPortfolioTable
- 6307daa: Task 2 — renderDonutChart + initBatchForm update

## Self-Check: PASSED

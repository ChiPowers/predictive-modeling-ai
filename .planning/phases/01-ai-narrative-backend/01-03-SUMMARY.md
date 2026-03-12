---
phase: 01-ai-narrative-backend
plan: 03
subsystem: ui
tags: [vanilla-js, html, css, anthropic, ai-narrative, fetch]

# Dependency graph
requires:
  - phase: 01-ai-narrative-backend-02
    provides: POST /ai/interpret endpoint returning {narrative} text
  - phase: 01-ai-narrative-backend-01
    provides: Research on API shape and frontend patterns
provides:
  - fetchNarrative() helper in app.js that POSTs to /ai/interpret
  - setNarrative() helper that shows/hides narrative paragraph elements
  - scoreNarrative, forecastNarrative, monitoringNarrative <p> elements in index.html
  - Monitoring Summary section in the UI with /monitoring/summary fetch
  - .narrative CSS class in styles.css
affects:
  - Phase 2 (any UI enhancements will extend these narrative elements)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - fetchNarrative() called after primary fetch with .then() so primary result displays before narrative loads
    - setNarrative() hides element via hidden attribute when narrative is null
    - All narrative failures silently degrade (catch returns null)

key-files:
  created: []
  modified:
    - service/static/app.js
    - service/static/index.html
    - service/static/styles.css

key-decisions:
  - "fetchNarrative uses .then() not await so primary result displays immediately while narrative loads async"
  - "Monitoring section added to index.html with auto-load on page bootstrap — no separate user action required to see monitoring narrative"
  - "CSS .narrative class uses --accent-soft background and --accent left-border from existing CSS variables"

patterns-established:
  - "Narrative pattern: primary fetch → setOutput() → setNarrative(null) [clear] → fetchNarrative().then(setNarrative)"
  - "Graceful degradation: narrative failures return null, hidden attribute keeps element invisible"

requirements-completed: [AI-01, AI-02, AI-03]

# Metrics
duration: 6min
completed: 2026-03-12
---

# Phase 1 Plan 03: AI Narrative Frontend Summary

**fetchNarrative() helper and three narrative <p> elements wired into score, forecast, and monitoring panels — plain-language AI interpretations now appear below each result when ANTHROPIC_API_KEY is set**

## Performance

- **Duration:** 6 min
- **Started:** 2026-03-12T20:04:17Z
- **Completed:** 2026-03-12T20:10:00Z
- **Tasks:** 3 of 3 (checkpoint:human-verify approved)
- **Files modified:** 3

## Accomplishments
- Added fetchNarrative() and setNarrative() helpers to app.js following existing readJson/setOutput patterns
- Wired narrative calls after score, forecast, and monitoring result handlers
- Added scoreNarrative, forecastNarrative, monitoringNarrative hidden `<p>` elements to index.html
- Added Monitoring Summary section to index.html (was missing) with auto-load and refresh button
- Added .narrative CSS class using existing CSS custom properties

## Task Commits

Each task was committed atomically:

1. **Task 1: Add fetchNarrative() and wire into score, forecast, monitoring handlers** - `58fe796` (feat)
2. **Task 2: Add narrative paragraph elements to index.html** - `29a71cb` (feat)

3. **Task 3: Checkpoint — human-verify full Phase 1 AI narrative integration** - approved by user

**Plan metadata:** pending (see final commit below)

## Files Created/Modified
- `service/static/app.js` - Added fetchNarrative(), setNarrative(), loadMonitoring(), initMonitoringSection(), wired into initScoreForm/initForecastForm/bootstrap
- `service/static/index.html` - Added scoreNarrative, forecastNarrative, monitoringNarrative <p> elements; added Monitoring Summary section
- `service/static/styles.css` - Added .narrative CSS class

## Decisions Made
- Used `.then()` instead of `await` for fetchNarrative so the primary result displays immediately while narrative loads asynchronously
- Added a full Monitoring Summary section to index.html since none existed — required for monitoringNarrative to have a context (auto-fix Rule 2: missing critical UI structure)
- CSS .narrative class uses `--accent-soft` for background and `--accent` for border, matching the existing design system

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical] Added Monitoring Summary section to index.html**
- **Found during:** Task 2 (Add narrative paragraph elements to index.html)
- **Issue:** The plan required adding `monitoringNarrative` after the monitoring output section, but no monitoring section existed in index.html. The monitoring endpoint `/monitoring/summary` existed in the backend (from prior plans) but had no frontend panel.
- **Fix:** Added a Monitoring Summary `<section class="card">` with a `monitoringView` `<pre>`, refresh button, and the `monitoringNarrative` `<p>` element. Also added `loadMonitoring()` and `initMonitoringSection()` in app.js.
- **Files modified:** service/static/index.html, service/static/app.js
- **Verification:** All 144 tests pass; node check confirms monitoringNarrative present
- **Committed in:** 29a71cb (Task 2), 58fe796 (Task 1)

---

**Total deviations:** 1 auto-fixed (1 missing critical)
**Impact on plan:** The missing monitoring section was required for the narrative to have anywhere to render. Auto-fix is essential for plan correctness. No scope creep.

## Issues Encountered
None.

## User Setup Required
**ANTHROPIC_API_KEY is required for AI narrative generation.** Without it:
- The server starts and all primary features work (score, forecast, monitoring data)
- The /ai/interpret endpoint returns 503 when called
- Narrative paragraphs remain hidden (graceful degradation)

To enable narratives: set `ANTHROPIC_API_KEY` in your environment before starting the server.
Source: Anthropic Console (console.anthropic.com) -> API Keys -> Create key.

## Next Phase Readiness
- Phase 1 fully complete — all three narrative panels verified in browser with real ANTHROPIC_API_KEY
- Graceful degradation confirmed: score/forecast/monitoring results unaffected when API key absent
- ANTHROPIC_API_KEY security confirmed: key never appears in any browser request or response
- Phase 2 can extend these narrative elements (e.g., factor contribution bars, richer monitoring UI)
- Monitoring section provides a new visible panel for future enhancement

---
*Phase: 01-ai-narrative-backend*
*Completed: 2026-03-12*

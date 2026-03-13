# Phase 3: Demo Flow + Portfolio Dashboard - Context

**Gathered:** 2026-03-12
**Status:** Ready for planning

<domain>
## Phase Boundary

Replace the 5-step numbered instruction list with a one-click animated demo flow that auto-runs the full pipeline (seed → train → activate → score → forecast) with step-by-step progress. Replace raw batch JSON output with a sortable portfolio table, donut distribution chart, and AI-generated portfolio insight. No new backend endpoints needed beyond calling existing /jobs, /models/activate, /score, /batch_score, /forecast, and /ai/interpret endpoints.

</domain>

<decisions>
## Implementation Decisions

### Demo Progress UI
- Animated checklist replaces the existing `<ol>` numbered list in the Jobs card
- Five steps with circle/checkmark icons: Seed demo data → Train pipeline → Activate model → Score loan → Run forecast
- Current step shows a spinning indicator; completed steps show a filled checkmark
- Manual job form (dropdowns + submit button) is hidden entirely — the demo button is the sole entry point
- After all steps complete: fixed copy appears — "Your portfolio is ready. Here's what the model found." — then auto-scroll to Portfolio section
- Button label resets to "Run Again"; checklist stays fully checked until the next run resets it
- Button text: "Run Full Demo" on first load, "Run Again" after completion

### Demo Error Handling
- Auto-retry each failed step once silently before surfacing an error
- If retry also fails: mark the step with a red ✗ and show a short inline error summary
- Full error traceback from the API response is collapsed by default; click to expand
- Remaining steps stay unchecked and greyed out after a failure
- On failure, show a "Restart from beginning" button — no mid-flow resume
- Job polling: every 3 seconds, 2-minute timeout before treating step as failed

### Portfolio Table
- Columns: Loan #, PD Score (%), Risk Tier (badge), Top Risk Factor
- Default sort: PD score descending (highest risk first)
- All four columns sortable client-side; clicking a header toggles ascending/descending
- Risk tier badges reuse the Phase 2 color system (Low = green, Moderate = amber, High/Very High = red)
- Replaces the `<pre id="batchView">` raw JSON output entirely

### Portfolio Distribution Chart
- SVG donut chart showing count per risk tier
- Arc segment colors match the gauge/badge palette: green (Low), amber (Moderate), orange (High), red (Very High)
- Each segment labeled with tier name and count

### Portfolio Layout
- Section order: table → donut chart → AI insight (PORT-03 narrative)
- AI insight calls existing /ai/interpret endpoint with batch score results
- No separate demo-summary API call — PORT-03 narrative is the demo conclusion

### Claude's Discretion
- Exact SVG donut dimensions, stroke width, and animation
- Checklist step icon design (filled circle, checkmark style)
- Spacing and typography for checklist and portfolio sections
- Transition/animation timing for step completion
- Exact error message copy (short summary in the inline collapse trigger)

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- `jobPayloadTemplates` in app.js (line 9): `seed-demo` and `pipeline` job payloads already defined — reuse directly in demo flow
- `/jobs/{jobType}` fetch pattern (line 317): existing job submission logic; demo flow reuses the same fetch call
- `/jobs?limit=20` polling pattern (line 292): demo flow polls this to detect job completion (status field)
- `/models/activate` fetch (line 353): existing activate call; demo flow calls this after pipeline job completes
- `fetchNarrative()` / `setNarrative()` pattern: batch AI insight (PORT-03) follows same pattern as score/forecast narratives
- Risk tier badge CSS from Phase 2: `.badge` variants (green/amber/red) already in styles.css — reuse for table
- `setOutput(id, data, isError)`: currently renders batch result to `#batchView` pre — this gets replaced

### Established Patterns
- Vanilla ES6, no framework — all new JS in `app.js`
- CSS custom properties for all colors (`--accent`, `--danger`, `--success`, `--warning`) — checklist icons and error states use these
- `<pre id="batchView">` is the current batch output element — remove and replace with table + chart + narrative
- `fetch → readJson → setOutput` pipeline for all API calls in app.js
- Job status check: poll `/jobs?limit=20` and find the job by type; `status === "completed"` or `status === "failed"`

### Integration Points
- Jobs card (`index.html`): `<ol>` numbered list replaced with `#demoChecklist` container and `#runDemoBtn` button
- `#batchForm` section (`index.html` ~line 155): add portfolio table, donut chart, and narrative paragraph below/replacing `#batchView`
- New `runFullDemo()` function in app.js: orchestrates the 5-step sequence using existing fetch patterns
- `scoreNarrative`, `forecastNarrative` paragraphs already in DOM — `batchNarrative` follows same pattern

</code_context>

<specifics>
## Specific Ideas

- Auto-retry silently on first failure — the retry uses the error traceback from the API response as implicit feedback context (no mutation of the request, just a clean retry)
- Checklist stays completed (all checkmarks) after demo finishes — it's a record of what ran, not a reset UI
- The completion message "Your portfolio is ready. Here's what the model found." appears as static copy in the checklist area before the auto-scroll — no Claude API call for this copy

</specifics>

<deferred>
## Deferred Ideas

- None — discussion stayed within phase scope

</deferred>

---

*Phase: 03-demo-flow-portfolio-dashboard*
*Context gathered: 2026-03-12*

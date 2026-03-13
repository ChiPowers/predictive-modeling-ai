---
phase: 03-demo-flow-portfolio-dashboard
verified: 2026-03-12T23:00:00Z
status: human_needed
score: 11/11 automated must-haves verified
re_verification: false
human_verification:
  - test: "Click Run Full Demo button and watch all 5 steps animate"
    expected: "Each step transitions from pending (dim circle) to active (spinning border) to done (green checkmark) in sequence. After all 5 complete, 'Your portfolio is ready. Here's what the model found.' appears and the page auto-scrolls to the Batch Score section."
    why_human: "CSS keyframe animations (spin), data-state transitions, requestAnimationFrame scroll, and visual feedback cannot be asserted by pytest."
  - test: "Submit Batch Score form and inspect the portfolio table"
    expected: "A 4-column table (Loan #, PD Score %, Risk Tier, Top Risk Factor) appears. Risk Tier cells show color-coded badges. Clicking a column header sorts rows; clicking again reverses direction."
    why_human: "DOM rendering, badge color appearance, and interactive sort behavior require a browser."
  - test: "Inspect the donut chart after Batch Score submit"
    expected: "A donut SVG appears with arc segments in green (Low), amber (Moderate), orange (High), red (Very High). Each segment is labeled with tier name and count. Single-tier result shows a filled circle, not a partial arc."
    why_human: "SVG visual rendering and color correctness cannot be verified programmatically."
  - test: "Confirm AI insight paragraph appears below the donut chart"
    expected: "A non-generic paragraph specific to the portfolio appears (e.g. count, average PD, recommended action). It is not a JSON dump or generic error text."
    why_human: "Content quality and element visibility require browser interaction. AI response content is non-deterministic."
  - test: "Click 'Run Again' after successful demo run"
    expected: "All step icons reset to dim pending circles before the new run starts. Button label changes to 'Running...' then returns to 'Run Again' on completion."
    why_human: "Animated reset and re-run timing is a visual/interactive behavior."
---

# Phase 3: Demo Flow and Portfolio Dashboard — Verification Report

**Phase Goal:** Build a guided demo flow and portfolio dashboard so visitors can experience the full ML pipeline end-to-end and see portfolio-level risk insights without manual setup.
**Verified:** 2026-03-12T23:00:00Z
**Status:** human_needed — all automated checks pass; 5 visual/interactive behaviors require human confirmation
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | POST /ai/interpret with context_type='batch' returns a portfolio-specific narrative | VERIFIED | `_build_prompt` batch branch exists at api.py:288; returns count, avg_pd%, high_risk count; `test_build_prompt_batch_context` + `test_ai_interpret_batch_context` both pass |
| 2 | test_demo_flow.py exists with 10 stubs covering all Phase 3 structural requirements | VERIFIED | File exists at tests/test_demo_flow.py with all 10 functions; `pytest tests/test_demo_flow.py` passes 10/10 |
| 3 | GET / contains #runDemoBtn and #demoChecklist with no numbered instruction list | VERIFIED | index.html:29 has `id="runDemoBtn"`; index.html:31 has `id="demoChecklist"`; no `<ol>` in Run Demo card |
| 4 | GET / contains five .demo-step elements and a #demoComplete element | VERIFIED | index.html:32-52 has exactly 5 `<li class="demo-step">`; index.html:53 has `id="demoComplete"` |
| 5 | GET / contains #portfolioTable, #portfolioDonut, and #batchNarrative — no #batchView | VERIFIED | index.html:221-223 has all three; no `id="batchView"` in index.html or app.js |
| 6 | jobForm has hidden attribute at page load | VERIFIED | index.html:58: `<form id="jobForm" class="stack" hidden>` |
| 7 | app.js contains runFullDemo(), startDemo(), initDemoButton(), setStepState(), pollJobById(), submitJobWithRetry(), showDemoError() | VERIFIED | All 7 functions present in app.js (lines 396-603); bootstrap() calls initDemoButton() as first line (line 753) |
| 8 | Polling uses 'succeeded'/'failed' — never 'completed' | VERIFIED | app.js:405: `job.status === 'succeeded'`; `grep completed app.js` returns empty |
| 9 | renderPortfolioTable(), renderDonutChart(), polarToCartesian(), arcPath() exist in app.js | VERIFIED | All four present; portfolioSort is module-level at line 606; initBatchForm() calls renderPortfolioTable and renderDonutChart |
| 10 | initBatchForm() calls fetchNarrative('batch', ...) and setNarrative('batchNarrative', ...) — not setOutput('batchView', ...) | VERIFIED | app.js:286-287 confirm correct wiring; no batchView reference in app.js |
| 11 | styles.css has .demo-step state rules and #portfolioTable/#portfolioDonut rules | VERIFIED | 11 occurrences of demo-step; #portfolioTable rules at line 387; #portfolioDonut at line 433 |

**Score:** 11/11 automated truths verified

---

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `tests/test_demo_flow.py` | 10 test stubs for DEMO-01..04 + PORT-01..03 | VERIFIED | All 10 functions present; 10/10 pass in pytest |
| `service/api.py` | `elif context_type == "batch":` branch in `_build_prompt` | VERIFIED | Branch at line 288; correct implementation with count, avg_pd, high_risk calculation |
| `service/static/index.html` | Demo card restructure + portfolio DOM elements | VERIFIED | runDemoBtn, demoChecklist (5 steps), demoComplete, portfolioTable, portfolioDonut, batchNarrative all present; jobForm hidden; batchView removed |
| `service/static/styles.css` | .demo-step state rules + portfolio table/donut styles | VERIFIED | 11 demo-step rules; portfolioTable + portfolioDonut styles appended; no existing rules modified |
| `service/static/app.js` | Demo orchestration + portfolio render functions | VERIFIED | All required functions present; bootstrap wired; correct job status; no batchView references |

---

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `service/api.py _build_prompt` | portfolio-specific prompt | `elif context_type == "batch"` branch | WIRED | Returns count, avg_pd, high_risk; test_build_prompt_batch_context passes |
| `app.js runFullDemo()` | `/jobs/{jobType}` POST | `fetch('/jobs/${jobType}', ...)` in submitJobWithRetry | WIRED | app.js:416 — submits job, captures id, polls |
| `app.js pollJobById()` | `GET /jobs/{id}` | polls every 3s, checks `status === 'succeeded'` or `'failed'` | WIRED | app.js:404-409 — correct terminal statuses, no "completed" |
| `app.js runFullDemo()` | `#demoChecklist .demo-step` | `setStepState()` sets `data-state` attribute | WIRED | app.js:396-399; called at each step transition (active/done/failed) |
| `app.js initBatchForm()` | `renderPortfolioTable() + renderDonutChart()` | batch form submit handler | WIRED | app.js:284-285 — both called with `payload.results` |
| `app.js initBatchForm()` | `/ai/interpret` | `fetchNarrative('batch', payload).then(n => setNarrative('batchNarrative', n))` | WIRED | app.js:287 — correct context_type and target element |
| `renderDonutChart()` | `#portfolioDonut` | sets innerHTML to SVG; degenerate case uses `<circle>` | WIRED | app.js:691-747; circle fallback at lines 236-244 of the function |
| `bootstrap()` | `initDemoButton()` | first call inside bootstrap | WIRED | app.js:753: `initDemoButton();` is first line |

---

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| DEMO-01 | 03-01, 03-02, 03-03, 03-05 | Single "Run Full Demo" button replaces 5-step numbered list | SATISFIED | `id="runDemoBtn"` in index.html; no `<ol>` in Run Demo card; initDemoButton() wired |
| DEMO-02 | 03-01, 03-03, 03-05 | Auto-executes seed → pipeline → activate → score → forecast in sequence | SATISFIED | runFullDemo() implements 5-step sequence; submitJobWithRetry and pollJobById implement async orchestration |
| DEMO-03 | 03-01, 03-02, 03-03, 03-05 | Step-by-step animated progress (spinner active, checkmark done) | SATISFIED (automated) / NEEDS HUMAN (visual) | setStepState() sets data-state; CSS rules for pending/active/done/failed states present; animation requires human |
| DEMO-04 | 03-01, 03-02, 03-03, 03-05 | Ends with "Your portfolio is ready. Here's what the model found." | SATISFIED | `id="demoComplete"` in index.html:53 with correct text; runFullDemo() sets `complete.hidden = false` on success |
| PORT-01 | 03-01, 03-02, 03-04, 03-05 | Batch results show as sortable table (Loan #, PD, Risk Tier, Top Risk Factor) | SATISFIED (automated) / NEEDS HUMAN (sort UX) | renderPortfolioTable() implemented; initBatchForm wired; 4-column headers with aria-sort; sort UX requires browser |
| PORT-02 | 03-01, 03-02, 03-04, 03-05 | Distribution visualization — donut/bar chart by risk tier count | SATISFIED (automated) / NEEDS HUMAN (visual) | renderDonutChart() implemented with SVG arcs and circle fallback; #portfolioDonut DOM element present; visual correctness requires browser |
| PORT-03 | 03-01, 03-02, 03-04, 03-05 | Portfolio-level AI insight paragraph | SATISFIED | `_build_prompt('batch', ...)` returns portfolio-specific prompt; fetchNarrative wired to batchNarrative; test_ai_interpret_batch_context passes |

No orphaned requirements — all 7 IDs (DEMO-01..04, PORT-01..03) are claimed by at least one plan and verified with implementation evidence.

---

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `service/static/index.html` | 96 | `placeholder="leave blank for latest"` | Info | Input placeholder text — not a code stub; pre-existing UI from Phase 1 model activation form; no impact on Phase 3 goal |

No blockers. No stubs or empty implementations found in Phase 3 modified files.

---

### Human Verification Required

The following behaviors cannot be verified programmatically. A browser session against a running server is required.

**1. Demo flow step animations**

**Test:** Start the server (`uvicorn service.api:app --reload`), open http://localhost:8000, click "Run Full Demo"
**Expected:** Each step transitions: dim circle (pending) → spinning ring border (active) → solid green checkmark circle (done). Steps execute sequentially (one at a time). After step 5 completes, "Your portfolio is ready. Here's what the model found." appears. Page auto-scrolls to the Batch Score section. Button label changes to "Run Again".
**Why human:** CSS `@keyframes spin` animation, `data-state` visual transitions, `requestAnimationFrame` scroll, and button state changes all require a live browser.

**2. Demo error handling (if a step fails)**

**Test:** If any step fails during the demo run, observe the error state.
**Expected:** Failed step shows a red X icon. Remaining steps remain dimmed. A collapsible "Step failed" detail appears below the checklist with a "Restart from beginning" button. Clicking Restart resets all steps and re-runs.
**Why human:** Error display, collapsible details, and restart wiring require a live failure scenario.

**3. Portfolio table sort behavior**

**Test:** Submit the Batch Score form. Click a column header. Click again.
**Expected:** Rows re-sort on first click (ascending). Rows reverse on second click (descending). The `aria-sort` attribute on the active header shows a sort indicator. Risk Tier column shows color-coded badges (green/amber/orange/red).
**Why human:** DOM re-rendering on click, badge CSS rendering, and aria attribute visual feedback require a browser.

**4. Donut chart visual correctness**

**Test:** After Batch Score submit, inspect the donut chart below the table.
**Expected:** Arc segments appear in: green (#1a7f37) for Low, amber (#9a6700) for Moderate, orange (#d97706) for High, red (#b42318) for Very High. Each segment has a label showing tier name and count. The center shows total loan count. If all loans are one tier, a solid filled circle renders (not a broken arc).
**Why human:** SVG fill color rendering, arc geometry, and label positioning require visual inspection.

**5. AI insight content quality**

**Test:** After Batch Score submit, read the paragraph below the donut chart.
**Expected:** A non-generic, portfolio-specific paragraph (e.g., references loan count, average PD percentage, a concrete recommendation). Not raw JSON. Not an error message.
**Why human:** AI response content quality and element visibility require human judgment.

---

### Test Suite Results

- `pytest tests/test_demo_flow.py`: 10 passed (all Phase 3 tests green)
- `pytest tests/ -q`: 160 passed, 1 skipped, **1 pre-existing failure** (`test_forecast_missing_model_returns_503`)
  - This failure exists in `test_service_smoke.py`, last modified by the platform hardening commit (`1626cc5`) predating Phase 3 by multiple phases. The test expects a 503 when no model is loaded, but the test environment has a prophet model artifact present. This is a pre-existing environmental issue — not introduced or worsened by Phase 3.

---

### Gaps Summary

No gaps. All automated must-haves are verified. The phase is blocked only by the human visual verification items listed above, which are inherent to the nature of animated UI work (CSS animations, SVG rendering, JS timing) — not missing implementations.

---

_Verified: 2026-03-12T23:00:00Z_
_Verifier: Claude (gsd-verifier)_

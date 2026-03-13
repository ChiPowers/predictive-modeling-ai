# Phase 3: Demo Flow + Portfolio Dashboard - Research

**Researched:** 2026-03-12
**Domain:** Vanilla JS frontend orchestration, SVG donut chart, client-side sortable table, async job polling
**Confidence:** HIGH

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Demo Progress UI**
- Animated checklist replaces the existing `<ol>` numbered list in the Jobs card
- Five steps with circle/checkmark icons: Seed demo data → Train pipeline → Activate model → Score loan → Run forecast
- Current step shows a spinning indicator; completed steps show a filled checkmark
- Manual job form (dropdowns + submit button) is hidden entirely — the demo button is the sole entry point
- After all steps complete: fixed copy appears — "Your portfolio is ready. Here's what the model found." — then auto-scroll to Portfolio section
- Button label resets to "Run Again"; checklist stays fully checked until the next run resets it
- Button text: "Run Full Demo" on first load, "Run Again" after completion

**Demo Error Handling**
- Auto-retry each failed step once silently before surfacing an error
- If retry also fails: mark the step with a red x and show a short inline error summary
- Full error traceback from the API response is collapsed by default; click to expand
- Remaining steps stay unchecked and greyed out after a failure
- On failure, show a "Restart from beginning" button — no mid-flow resume
- Job polling: every 3 seconds, 2-minute timeout before treating step as failed

**Portfolio Table**
- Columns: Loan #, PD Score (%), Risk Tier (badge), Top Risk Factor
- Default sort: PD score descending (highest risk first)
- All four columns sortable client-side; clicking a header toggles ascending/descending
- Risk tier badges reuse the Phase 2 color system (Low = green, Moderate = amber, High/Very High = red)
- Replaces the `<pre id="batchView">` raw JSON output entirely

**Portfolio Distribution Chart**
- SVG donut chart showing count per risk tier
- Arc segment colors match the gauge/badge palette: green (Low), amber (Moderate), orange (High), red (Very High)
- Each segment labeled with tier name and count

**Portfolio Layout**
- Section order: table → donut chart → AI insight (PORT-03 narrative)
- AI insight calls existing /ai/interpret endpoint with batch score results
- No separate demo-summary API call — PORT-03 narrative is the demo conclusion

### Claude's Discretion
- Exact SVG donut dimensions, stroke width, and animation
- Checklist step icon design (filled circle, checkmark style)
- Spacing and typography for checklist and portfolio sections
- Transition/animation timing for step completion
- Exact error message copy (short summary in the inline collapse trigger)

### Deferred Ideas (OUT OF SCOPE)
- None — discussion stayed within phase scope
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| DEMO-01 | UI has a single "Run Full Demo" button that replaces the 5-step numbered instruction list | HTML restructure of Jobs card `<ol>` → `#demoChecklist` + `#runDemoBtn`; job form hidden |
| DEMO-02 | Demo flow auto-executes: seed-demo → pipeline → activate → score → forecast in sequence | `runFullDemo()` orchestration function; reuses `jobPayloadTemplates`, `/jobs/{type}`, `/jobs?limit=20` polling, `/models/activate`, `/score`, `/forecast` fetch patterns |
| DEMO-03 | Demo flow shows animated step-by-step progress (each step checks off as it completes) | CSS spinner + checkmark SVG inline; CSS custom properties for state colors; no external libs needed |
| DEMO-04 | Demo flow ends with a summary narrative: "Your portfolio is ready. Here's what the model found." | Static copy injected after final step completes; `scrollIntoView` for auto-scroll to portfolio section |
| PORT-01 | Batch score results display as a table (columns: loan #, PD score, risk tier, top risk factor) | `renderPortfolioTable()` replaces `<pre id="batchView">`; `getRiskTier()` already exists in app.js |
| PORT-02 | Batch score results include a distribution visualization (donut or bar chart by risk tier count) | SVG donut using polar-to-cartesian arc math; matches existing hand-rolled SVG pattern from forecast chart and gauge |
| PORT-03 | Batch score results include a portfolio-level AI insight | `fetchNarrative("batch", batchPayload)` → `setNarrative("batchNarrative", ...)` following existing narrative pattern; requires new "batch" context_type branch in `_build_prompt` in api.py |
</phase_requirements>

---

## Summary

Phase 3 is a pure frontend UX overhaul with one small backend addition. The frontend work is entirely in `service/static/app.js` and `service/static/index.html`, with one CSS addition to `service/static/styles.css`. No new API endpoints are needed. The only backend change is adding a "batch" context type to the existing `_build_prompt` function in `service/api.py` so `POST /ai/interpret` can handle portfolio-level narratives.

The demo flow replaces the static `<ol>` numbered list with a JavaScript-orchestrated checklist that fires steps sequentially: seed-demo job → poll to completion → pipeline job → poll to completion → activate model → populate and submit score form → run forecast. All of these fetch patterns already exist in `app.js`; `runFullDemo()` is new orchestration code that wires them together with polling, retry logic, and step-state rendering. Job polling uses `/jobs?limit=20` (already called by `refreshJobs()`) and matches by `job_type` field, checking for `"succeeded"` or `"failed"` status.

The portfolio dashboard replaces `<pre id="batchView">` with three new elements: a sortable `<table>`, an SVG donut chart, and a narrative paragraph. All rendering is client-side vanilla JS following existing SVG patterns. The `getRiskTier()` function and badge CSS classes from Phase 2 are directly reusable.

**Primary recommendation:** Build in a single wave — HTML restructure first, then `runFullDemo()` orchestration, then portfolio rendering functions. Test coverage uses the same FastAPI `TestClient` pattern as Phase 2.

---

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Vanilla ES6 JS | — | All frontend logic | Project locked decision; no framework |
| SVG (inline) | — | Donut chart, step icons | Established pattern in project (forecast chart, score gauge) |
| CSS custom properties | — | Colors, animation states | Already in use across entire stylesheet |
| FastAPI TestClient | 0.111.1 | Backend structural tests | Existing test pattern for all phases |
| pytest | via pyproject.toml | Test runner | `testpaths = ["tests"]`, `addopts = "-v"` |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `scrollIntoView()` | Browser native | Auto-scroll to portfolio after demo | DEMO-04: triggers after completion message |
| `details`/`summary` HTML elements | Browser native | Collapsible error traceback | Error handling — no JS needed for expand/collapse |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Hand-rolled SVG donut | Chart.js / D3 | External dep not warranted; existing SVG pattern covers the need |
| CSS spinner animation | Lottie animation | Overkill; CSS `@keyframes` matches existing `fade-in` pattern |
| `scrollIntoView` | Custom scroll | Native API is sufficient |

**Installation:** No new packages needed.

---

## Architecture Patterns

### File Locations
```
service/static/
├── index.html       # HTML: replace <ol>, add checklist, replace #batchView
├── app.js           # JS: runFullDemo(), renderPortfolioTable(), renderDonutChart()
└── styles.css       # CSS: checklist step states, table, donut chart
service/api.py       # Backend: add "batch" branch in _build_prompt()
tests/
└── test_demo_flow.py  # New: structural HTML assertions + batch context_type test
```

### Pattern 1: Job Polling Loop
**What:** Submit a job, then poll `/jobs?limit=20` every 3 seconds until `status === "succeeded"` or `"failed"` (note: backend uses `"succeeded"` not `"completed"` — confirmed in `service/jobs.py`).
**When to use:** Steps 1 (seed-demo) and 2 (pipeline) in demo flow — both are async background jobs.

```javascript
// Pattern: poll until terminal status, with timeout
async function pollJobByType(jobType, intervalMs = 3000, timeoutMs = 120000) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    const list = await fetch('/jobs?limit=20').then(readJson);
    // match most-recent job of the given type
    const job = list.jobs.find(j => j.job_type === jobType);
    if (job?.status === 'succeeded') return job;
    if (job?.status === 'failed') throw new Error(job.error || 'Job failed');
    await new Promise(res => setTimeout(res, intervalMs));
  }
  throw new Error(`Timeout waiting for ${jobType} job`);
}
```

**Critical detail:** Job status values are `"queued"`, `"running"`, `"succeeded"`, `"failed"` — NOT `"completed"`. The CONTEXT.md says "completed" but the actual `service/jobs.py` uses `"succeeded"`. Use `"succeeded"`.

### Pattern 2: Step State Machine
**What:** Each checklist step has three visual states — pending (grey circle), active (spinner), done (filled checkmark), failed (red x).
**When to use:** Driven by `runFullDemo()` as it advances through the 5-step sequence.

```javascript
// State transitions: 'pending' → 'active' → 'done' | 'failed'
function setStepState(stepIndex, state) {
  const step = document.querySelectorAll('.demo-step')[stepIndex];
  step.dataset.state = state;  // CSS handles all visual rendering via [data-state]
}
```

### Pattern 3: Client-Side Sort
**What:** Table headers toggle sort direction on click; re-renders table rows by sorted data array.
**When to use:** All four portfolio table columns.

```javascript
// Sort state: { col: 'pd', dir: 'desc' }
// On header click: toggle dir if same col, else reset to 'asc'
// Re-render rows from sorted array — no DOM manipulation, full innerHTML replace
function renderPortfolioTable(results, sortState) {
  const sorted = [...results].sort((a, b) => {
    const val = sortState.dir === 'asc' ? 1 : -1;
    return a[sortState.col] > b[sortState.col] ? val : -val;
  });
  // build tbody rows — getRiskTier() gives badge class
}
```

### Pattern 4: SVG Donut Chart
**What:** Four arc segments (one per risk tier) drawn with SVG `<path>` elements using polar-to-cartesian math.
**When to use:** PORT-02 distribution visualization.

```javascript
// Polar to cartesian helper
function polarToCartesian(cx, cy, r, angleDeg) {
  const rad = (angleDeg - 90) * Math.PI / 180;
  return { x: cx + r * Math.cos(rad), y: cy + r * Math.sin(rad) };
}

// Arc path for a segment: startAngle, endAngle (degrees), cx, cy, r
function arcPath(cx, cy, r, startAngle, endAngle) {
  const s = polarToCartesian(cx, cy, r, startAngle);
  const e = polarToCartesian(cx, cy, r, endAngle);
  const large = endAngle - startAngle > 180 ? 1 : 0;
  return `M ${s.x} ${s.y} A ${r} ${r} 0 ${large} 1 ${e.x} ${e.y}`;
}
```

**Tier colors:** Map directly to existing CSS custom properties:
- Low → `var(--success)` (#1a7f37)
- Moderate → `var(--warning)` (#9a6700)
- High → `#d97706` (orange — discretionary, between warning and danger)
- Very High → `var(--danger)` (#b42318)

### Pattern 5: Narrative for Batch Context
**What:** New `"batch"` branch in `_build_prompt()` in `service/api.py` to support `POST /ai/interpret` with batch score results.
**When to use:** PORT-03 — called after `renderPortfolioTable()` with the full batch response.

The existing `fetchNarrative("batch", batchPayload)` call pattern works today, but falls through to the generic fallback (`f"Interpret the following model output: {data}"`). A proper "batch" branch in `_build_prompt` produces better output.

```python
elif context_type == "batch":
    results = data.get("results", [])
    count = len(results)
    high_risk = sum(1 for r in results if r.get("pd", 0) >= 0.50)
    avg_pd = sum(r.get("pd", 0) for r in results) / count if count else 0
    return (
        f"A portfolio of {count} loans was scored. "
        f"Average default probability: {avg_pd:.0%}. "
        f"{high_risk} of {count} loans are high-risk (PD >= 50%). "
        "Write a 2-3 sentence plain-language portfolio summary. "
        "Include a concrete recommended action for the portfolio manager."
    )
```

### Anti-Patterns to Avoid
- **Using `"completed"` as job terminal status:** The backend uses `"succeeded"` and `"failed"`. Code that checks for `"completed"` will poll forever.
- **Polling `/jobs?limit=20` and sorting by index position:** Jobs are sorted by `created_at` descending. Match by `job_type` on the most-recent entry; a stale succeeded job from a previous run should be ignored. Submit the job first, capture the `id`, then poll `/jobs/{job_id}` directly — simpler and avoids stale match.
- **Triggering batch score from the demo flow as a separate job:** The demo flow calls `/score` (single) and `/forecast`, not `/batch_score`. The portfolio table is populated from the *existing* batch form submit or separately — re-read CONTEXT.md: the demo flow seeds data → trains → activates → scores ONE loan → forecasts. The portfolio section is the batch form result, not the demo result.
- **Resetting checklist after demo completes:** Decision: checklist stays fully checked. Only reset when "Run Again" is clicked.
- **Building a collapse widget from scratch:** Use `<details>`/`<summary>` HTML elements for the expandable error traceback — no JS needed.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Step spinner animation | Custom JS timer animation | CSS `@keyframes rotate` on a border-radius element | Pure CSS, no JS needed, consistent with existing fade-in pattern |
| Risk tier classification | Inline if/else in table render | Existing `getRiskTier(pd)` in app.js | Already correct, already tested |
| Expandable error traceback | Custom JS accordion | `<details>` / `<summary>` HTML | Browser-native, accessible, zero JS |
| SVG arc math for single point (100% of tier) | Special-case logic | Draw a full circle instead of an arc when count = total | Avoids degenerate arc path that renders nothing |

---

## Common Pitfalls

### Pitfall 1: Job Status "succeeded" vs "completed"
**What goes wrong:** Polling loop never exits because code checks `status === "completed"` but backend emits `"succeeded"`.
**Why it happens:** CONTEXT.md says "completed or failed" but that documents the conceptual state, not the wire value.
**How to avoid:** Always use `"succeeded"` and `"failed"` — confirmed in `service/jobs.py` lines 74 and 80.
**Warning signs:** Demo flow hangs at step 1 indefinitely despite job appearing in jobsView as done.

### Pitfall 2: Polling by job_type vs job_id
**What goes wrong:** A previous successful "seed-demo" job from an earlier run matches the type filter and the polling loop exits immediately (stale match).
**Why it happens:** `/jobs?limit=20` returns all recent jobs sorted newest-first; a match on `job_type` could pick up an old run.
**How to avoid:** Capture the `id` from the POST response, then poll `/jobs/{job_id}` directly. This is the unambiguous path.
**Warning signs:** Demo "completes" instantly without actually running anything.

### Pitfall 3: SVG Donut Degenerate Arc (100% single tier)
**What goes wrong:** When all loans are in one tier, the arc start and end points are the same, producing a zero-length invisible path.
**Why it happens:** SVG arc commands cannot represent a full circle with a single arc path element.
**How to avoid:** Detect the 100% case; render a full `<circle>` element instead of `<path>` arcs when only one tier has all loans.
**Warning signs:** Donut chart appears blank when all test loans are the same tier.

### Pitfall 4: Sort State Not Preserved After Re-render
**What goes wrong:** Table renders correctly on first batch result, but clicking a header sorts correctly once then breaks on the next batch score.
**Why it happens:** Sort state stored in a local variable gets garbage-collected when the function exits; re-render reads undefined.
**How to avoid:** Store sort state at module scope (e.g., `let portfolioSort = { col: 'pd', dir: 'desc' };`) so it persists across renders.
**Warning signs:** Sort works once, then resets to default on second click.

### Pitfall 5: Auto-scroll Fires Before DOM Update
**What goes wrong:** `scrollIntoView()` is called before the portfolio section has visible content, so scroll position looks wrong.
**Why it happens:** `scrollIntoView` executes synchronously; if called before `renderPortfolioTable` updates the DOM, the section height is still zero.
**How to avoid:** Call `scrollIntoView` after `renderPortfolioTable` and `renderDonutChart` have written to the DOM.
**Warning signs:** Page scrolls to the right position but the table appears blank for a frame.

### Pitfall 6: Demo Re-run Without State Reset
**What goes wrong:** Clicking "Run Again" without resetting checklist state causes steps to appear already-done before they run.
**Why it happens:** Step `data-state` attributes retain their previous values.
**How to avoid:** At the start of `runFullDemo()`, reset all step states to `"pending"` and re-enable the button label "Running...".
**Warning signs:** All checkmarks appear immediately on "Run Again" click.

---

## Code Examples

### Existing getRiskTier (already in app.js — reuse directly)
```javascript
// Source: service/static/app.js line 136
function getRiskTier(pd) {
  if (pd < 0.25) return { label: 'Low',       cls: 'badge-success' };
  if (pd < 0.50) return { label: 'Moderate',  cls: 'badge-warning' };
  if (pd < 0.75) return { label: 'High',      cls: 'badge-danger'  };
  return               { label: 'Very High',  cls: 'badge-danger'  };
}
```

### Existing fetchNarrative / setNarrative (reuse exactly this pattern)
```javascript
// Source: service/static/app.js line 44-62
// Call after renderPortfolioTable():
setNarrative("batchNarrative", null);
fetchNarrative("batch", batchPayload).then(n => setNarrative("batchNarrative", n));
```

### BatchScoreResponse shape (confirmed from service/schemas.py)
```javascript
// POST /batch_score returns:
// { results: [ { pd: 0.34, decision: "current", top_factors: [{name: "orig_ltv", value: 0.12}, ...] }, ... ], count: 4 }
// top_factors[0].name is the Top Risk Factor column value
```

### Job submission and response (confirmed from service/api.py)
```javascript
// POST /jobs/seed-demo → { id: "abc123", job_type: "seed-demo", status: "queued", ... }
// GET /jobs/{id} → { id: "abc123", status: "succeeded"|"running"|"queued"|"failed", error: null|"msg" }
// Terminal states: "succeeded", "failed"
```

### Existing SVG inline pattern (reference for donut style)
```javascript
// Source: service/static/app.js line 143 — renderScoreGauge
// Uses viewBox, role="img", aria-label, CSS custom properties for color
// Donut chart should follow same conventions
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Manual 5-step `<ol>` instruction list | One-click animated checklist | Phase 3 | Eliminates all manual user steps |
| Raw JSON in `<pre id="batchView">` | Sortable table + donut chart + narrative | Phase 3 | Portfolio results become human-readable |
| No batch AI insight | PORT-03 narrative via /ai/interpret "batch" context | Phase 3 | Closes the demo loop with a conclusion |

**Deprecated/outdated:**
- `<ol>` in the Run Demo card: removed entirely, replaced with `#demoChecklist`
- `<pre id="batchView">`: removed entirely, replaced with `#portfolioTable`, `#portfolioDonut`, `#batchNarrative`
- `initBatchForm()` submit handler rendering to `batchView`: updated to call `renderPortfolioTable()` + `renderDonutChart()` + `fetchNarrative("batch", ...)`

---

## Open Questions

1. **Does `runFullDemo()` also trigger batch score, or just single score + forecast?**
   - What we know: CONTEXT.md step sequence is "seed → pipeline → activate → score → forecast" — there is no explicit batch_score step in the demo flow.
   - What's unclear: The portfolio table is populated by the `initBatchForm()` handler, not by `runFullDemo()`. The demo auto-scrolls to Portfolio section but the batch table would be empty unless triggered separately.
   - Recommendation: Confirm with planner whether demo flow should also auto-submit batch score after forecast. If yes, add as step 5.5 between forecast and the summary message. If no, the portfolio table requires manual batch form submission and the auto-scroll just draws attention to it.

2. **"batch" context_type in /ai/interpret — should this be guarded or fail gracefully?**
   - What we know: Current `_build_prompt` has an `else` branch that produces a generic prompt for unknown context types — so calling with `"batch"` today works but produces low-quality output.
   - What's unclear: Whether the planner should treat backend `_build_prompt` update as a required sub-task or optional polish.
   - Recommendation: Include as a required task — the PORT-03 narrative quality depends on it.

---

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (via pyproject.toml `[tool.pytest.ini_options]`) |
| Config file | `pyproject.toml` — `testpaths = ["tests"]`, `addopts = "-v"` |
| Quick run command | `pytest tests/test_demo_flow.py -x -q` |
| Full suite command | `pytest tests/ -x -q` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| DEMO-01 | GET / contains `#runDemoBtn` and `#demoChecklist`; does NOT contain `<ol>` instruction list | structural/HTML | `pytest tests/test_demo_flow.py::test_demo_button_html_structure -x` | ❌ Wave 0 |
| DEMO-01 | GET / does NOT contain manual job form `<form id="jobForm">` visible (or form is hidden) | structural/HTML | `pytest tests/test_demo_flow.py::test_job_form_hidden -x` | ❌ Wave 0 |
| DEMO-02 | Integration: POST /jobs/seed-demo → 202; GET /jobs/{id} status reaches "succeeded" | integration | `pytest tests/test_demo_flow.py::test_seed_demo_job_submits -x` | ❌ Wave 0 |
| DEMO-03 | GET / contains five `.demo-step` elements or `data-step` elements | structural/HTML | `pytest tests/test_demo_flow.py::test_checklist_five_steps -x` | ❌ Wave 0 |
| DEMO-04 | GET / contains completion message text (static copy present in DOM, initially hidden) | structural/HTML | `pytest tests/test_demo_flow.py::test_completion_message_element -x` | ❌ Wave 0 |
| PORT-01 | GET / contains `#portfolioTable`; does NOT contain `id="batchView"` | structural/HTML | `pytest tests/test_demo_flow.py::test_portfolio_table_structure -x` | ❌ Wave 0 |
| PORT-02 | GET / contains `#portfolioDonut` | structural/HTML | `pytest tests/test_demo_flow.py::test_portfolio_donut_element -x` | ❌ Wave 0 |
| PORT-03 | GET / contains `#batchNarrative`; POST /ai/interpret with context_type="batch" returns narrative string | structural + unit | `pytest tests/test_demo_flow.py::test_batch_narrative_element tests/test_demo_flow.py::test_ai_interpret_batch_context -x` | ❌ Wave 0 |
| PORT-03 | `_build_prompt("batch", {...})` produces a non-generic prompt mentioning count/pd/high-risk | unit | `pytest tests/test_demo_flow.py::test_build_prompt_batch_context -x` | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** `pytest tests/test_demo_flow.py -x -q`
- **Per wave merge:** `pytest tests/ -x -q`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_demo_flow.py` — covers DEMO-01, DEMO-02, DEMO-03, DEMO-04, PORT-01, PORT-02, PORT-03
- [ ] No framework config gap — pytest already configured in pyproject.toml

*(No conftest.py gaps — existing `tests/__init__.py` and TestClient pattern are sufficient)*

---

## Sources

### Primary (HIGH confidence)
- `service/static/app.js` — full read; existing fetch patterns, job polling pattern, `getRiskTier`, `fetchNarrative`, `setNarrative`, `renderScoreGauge` SVG pattern
- `service/static/index.html` — full read; current DOM structure, element IDs, `<ol>` to replace, `<pre id="batchView">` to replace
- `service/static/styles.css` — full read; CSS custom properties, badge classes, existing animation patterns
- `service/api.py` — targeted read; `_build_prompt` branches (lines 236-289), `/batch_score` endpoint (lines 642-669), `/jobs` endpoints
- `service/jobs.py` — full read; job status values (`"queued"`, `"running"`, `"succeeded"`, `"failed"`), job schema fields
- `service/schemas.py` — partial read; `BatchScoreResponse`, `ScoreResponse`, `Factor` shapes
- `tests/test_score_panel.py` — full read; Phase 2 test pattern to replicate
- `tests/test_jobs_api.py` — partial read; job polling pattern in tests
- `pyproject.toml` — pytest config confirmed

### Secondary (MEDIUM confidence)
- CONTEXT.md decisions — comprehensive; all locked decisions treated as authoritative
- REQUIREMENTS.md — all Phase 3 requirements confirmed pending

### Tertiary (LOW confidence)
- None

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — entire stack confirmed from codebase read; no external dependencies
- Architecture: HIGH — all patterns derived from existing code in project; no speculation
- Pitfalls: HIGH — job status values confirmed from source; SVG arc degenerate case is standard geometry
- Test map: HIGH — pytest config confirmed; test file pattern confirmed from Phase 2 tests

**Research date:** 2026-03-12
**Valid until:** 2026-04-12 (stable — vanilla JS + FastAPI, no fast-moving dependencies)

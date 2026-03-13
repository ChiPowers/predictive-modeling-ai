# Phase 4: Monitoring Panel - Research

**Researched:** 2026-03-13
**Domain:** Vanilla JS frontend UI, FastAPI backend, PSI drift visualization
**Confidence:** HIGH

## Summary

Phase 4 transforms the existing "Monitoring Summary" section in `index.html` from a raw JSON `<pre>` dump into a rich "Model Health" panel. All backend infrastructure is already in place: `GET /monitoring/summary` returns `MonitoringSummaryResponse`, `POST /ai/interpret` with `context_type="monitoring"` returns AI narrative, and report JSON files exist on disk. Zero backend work is required.

The work is entirely frontend: replace `<pre id="monitoringView">` and its siblings with structured HTML containers, write a `renderMonitoringPanel()` function in `app.js` using the same SVG/badge/narrative patterns already established in Phases 1–3, and add scoped CSS rules following the existing `.factor-bars` / `#portfolioTable` style. PSI thresholds are already standardized in the backend (`PSI_WARN=0.10`, `PSI_ALERT=0.25`) but the requirements specify slightly different frontend thresholds (green <0.1, yellow 0.1–0.2, red >0.2); these are the display thresholds to implement in JS.

**Primary recommendation:** Replace the `monitoringView` pre with three semantic containers (`#driftIndicators`, `#modelAucRow`, `#monitoringNarrative`), render color-coded feature badges from `drift_features`, extract AUC + trend from `perf_drift`, and load the AI narrative with the existing `fetchNarrative` pattern. Handle `available=false` gracefully with a "No monitoring data yet" placeholder.

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| MON-01 | UI has a "Model Health" section that loads data from GET /monitoring/summary | Endpoint fully implemented; `loadMonitoring()` already calls it; need to replace `setOutput("monitoringView", payload)` with structured render function |
| MON-02 | Model Health displays feature drift indicators (green/yellow/red) per feature based on PSI thresholds (green <0.1, yellow 0.1–0.2, red >0.2) | `drift_features` key in response provides `{psi, severity, alert}` per feature; existing `.badge-success/.badge-warning/.badge-danger` CSS classes map directly |
| MON-03 | Model Health displays current AUC value and a simple trend indicator | `perf_drift.latest_auc` and `perf_drift.trend` ("improving"/"degrading"/"insufficient_data") are in the response; no new backend logic needed |
| MON-04 | Model Health displays AI-written status summary (uses AI-03 narrative) | `fetchNarrative("monitoring", payload)` already wired in `loadMonitoring()`; only need `setNarrative("monitoringNarrative", ...)` to unhide a properly styled element |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Vanilla JS (ES2020) | n/a | Frontend rendering | Project constraint — no framework |
| Inline SVG | n/a | Visual indicators | Established pattern (gauge, donut) |
| CSS custom properties | n/a | Theming | Existing `--success/--warning/--danger` vars |
| FastAPI TestClient | existing | Backend contract tests | Used throughout test suite |
| pytest | existing | Test runner | `pyproject.toml` configured |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| Existing `.badge-*` CSS classes | n/a | PSI color indicators | MON-02 drift badges per feature |
| Existing `.narrative` CSS class | n/a | AI narrative block | MON-04 narrative display |
| Existing `fetchNarrative()` | n/a | Async AI narrative fetch | MON-04 |
| Existing `setNarrative()` | n/a | Show/hide narrative element | MON-04 |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Badge-per-feature grid | SVG heatmap | Badges simpler, already styled, consistent with score tier badges |
| Inline AUC display | Sparkline chart | Sparkline is V2 requirement (V2-VIZ-02); simple text+badge is Phase 4 scope |
| Full panel rewrite | Extend existing pre | Structured HTML delivers the visual density required by MON-02/03 |

## Architecture Patterns

### Recommended Project Structure

No new files required. Changes are confined to:

```
service/static/
├── index.html    # Replace monitoringView pre with semantic containers
├── app.js        # Replace setOutput call with renderMonitoringPanel()
└── styles.css    # Add #driftIndicators grid and .drift-feature rules
```

Test additions:
```
tests/
└── test_api_contract.py   # Add test_monitoring_summary_html_contract
```

### Pattern 1: Semantic Container Swap (established Phase 3 precedent)

**What:** Replace generic `<pre>` output element with purpose-built containers that JS renders into.
**When to use:** Every time structured data replaces raw JSON dump.
**Example (Phase 3 precedent in index.html):**
```html
<!-- Before (generic) -->
<pre id="batchView" class="mono">No batch results yet.</pre>

<!-- After (semantic containers) -->
<div id="portfolioTable"></div>
<div id="portfolioDonut"></div>
<p id="batchNarrative" class="narrative" hidden></p>
```

**For Phase 4, apply the same swap to the Monitoring Summary section:**
```html
<!-- Remove -->
<pre id="monitoringView" class="mono">Loading monitoring data...</pre>

<!-- Add -->
<div id="driftIndicators"></div>
<div id="modelAucRow"></div>
<p id="monitoringNarrative" class="narrative" hidden></p>
```

### Pattern 2: PSI Threshold → Badge Class Mapping

**What:** Map numeric PSI value to badge CSS class using the required display thresholds.
**Note:** The backend uses `PSI_WARN=0.10` and `PSI_ALERT=0.25`. The requirements specify display thresholds of <0.1 green, 0.1–0.2 yellow, >0.2 red. These differ slightly from the backend alert threshold (0.25). Implement the frontend thresholds from the requirements, not the backend constant.

```javascript
// Source: requirements MON-02 + existing getRiskTier pattern in app.js
function getDriftClass(psi) {
  if (psi < 0.1)  return 'badge-success';
  if (psi <= 0.2) return 'badge-warning';
  return 'badge-danger';
}
```

### Pattern 3: AUC + Trend Display

**What:** Show latest AUC as a number and trend as a text indicator.
**Data source:** `perf_drift.latest_auc` (float or null), `perf_drift.trend` ("improving" | "degrading" | "insufficient_data").
**Graceful degradation:** When `latest_auc` is null (labels not yet available), show "AUC: Not yet available".

```javascript
// Source: perf_drift.py run_perf_drift return schema
function renderAucRow(perfDrift) {
  const container = document.getElementById('modelAucRow');
  if (!container) return;
  if (!perfDrift || perfDrift.latest_auc == null) {
    container.innerHTML = '<p class="chart-summary">AUC: Not yet available (labels pending)</p>';
    return;
  }
  const auc = perfDrift.latest_auc.toFixed(2);
  const trend = perfDrift.trend || 'unknown';
  const trendBadge = trend === 'improving'
    ? '<span class="badge badge-success">Improving</span>'
    : trend === 'degrading'
      ? '<span class="badge badge-danger">Degrading</span>'
      : '<span class="badge">Stable</span>';
  container.innerHTML = `<p class="chart-summary">AUC: <strong>${auc}</strong> ${trendBadge}</p>`;
}
```

### Pattern 4: Drift Feature Grid

**What:** Render one badge per feature showing its name and PSI severity color.
**Data source:** `drift_features` is `{[featureName]: {psi, severity, alert, ...}}`.

```javascript
// Source: MonitoringSummaryResponse schema in service/schemas.py
function renderDriftIndicators(driftFeatures) {
  const container = document.getElementById('driftIndicators');
  if (!container) return;
  if (!driftFeatures || Object.keys(driftFeatures).length === 0) {
    container.innerHTML = '<p class="chart-summary">No drift data available.</p>';
    return;
  }
  const badges = Object.entries(driftFeatures).map(([name, data]) => {
    const cls = getDriftClass(data.psi || 0);
    const psiLabel = (data.psi || 0).toFixed(3);
    return `<span class="badge ${cls} drift-feature-badge" title="PSI: ${psiLabel}">${name}</span>`;
  }).join('');
  container.innerHTML = `
    <p class="chart-summary drift-legend">Feature drift (PSI): <span class="drift-key drift-ok">green &lt;0.1</span> · <span class="drift-key drift-warn">yellow 0.1–0.2</span> · <span class="drift-key drift-alert">red &gt;0.2</span></p>
    <div class="drift-badges">${badges}</div>`;
}
```

### Pattern 5: renderMonitoringPanel() Orchestrator

**What:** Single entry point called from `loadMonitoring()` instead of `setOutput()`.
**Integration point:** Replace the `setOutput("monitoringView", monitoringPayload)` call.

```javascript
function renderMonitoringPanel(payload) {
  if (!payload.available) {
    const container = document.getElementById('driftIndicators');
    if (container) container.innerHTML = '<p class="chart-summary">No monitoring data yet. Run a monitoring job to see results.</p>';
    return;
  }
  renderDriftIndicators(payload.drift_features);
  renderAucRow(payload.perf_drift);
}
```

### Anti-Patterns to Avoid

- **Replacing `monitoringNarrative` element:** The `<p id="monitoringNarrative">` already exists in `index.html` and is correctly wired in `loadMonitoring()`. Do not rename or duplicate it.
- **Calling `setOutput("monitoringView", ...)` after adding visual containers:** Once the `<pre>` is removed, delete the `setOutput` call in `loadMonitoring()` to avoid a JS null reference.
- **Hardcoding PSI thresholds from the backend:** Backend uses 0.25 for alert; requirements specify 0.2 for red. Use the requirements value (0.2) in the frontend `getDriftClass()`.
- **Blocking the narrative on panel render:** The established pattern is `.then(n => setNarrative(...))` — narrative loads after primary data displays.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| PSI color mapping | Custom color scale | Existing `.badge-success/.badge-warning/.badge-danger` CSS classes | Already themed, visually consistent |
| AI narrative fetch | New HTTP wrapper | Existing `fetchNarrative("monitoring", payload)` | Already implemented and tested |
| Trend text display | Chart/sparkline | Simple text + badge | Sparkline is V2 scope; text is sufficient for Phase 4 |
| "Not available" state | Error overlay | Graceful inline message in the container div | Consistent with `renderPortfolioTable` pattern |

**Key insight:** Every rendering primitive needed for this panel already exists in `app.js` or `styles.css`. Phase 4 is assembly, not invention.

## Common Pitfalls

### Pitfall 1: PSI Threshold Mismatch
**What goes wrong:** Developer reads `PSI_ALERT = 0.25` from `monitoring/drift.py` and uses 0.25 as the red threshold in the frontend.
**Why it happens:** Backend constant differs from the requirements-specified display threshold (>0.2 = red).
**How to avoid:** Use requirements MON-02 thresholds in `getDriftClass()`: `< 0.1` green, `0.1–0.2` yellow, `> 0.2` red.
**Warning signs:** Red indicators not showing for features with PSI 0.21–0.24.

### Pitfall 2: Stale `monitoringView` Pre Reference
**What goes wrong:** After removing `<pre id="monitoringView">` from HTML, `setOutput("monitoringView", ...)` in `loadMonitoring()` silently fails or throws because `getElementById` returns null.
**Why it happens:** `loadMonitoring()` currently calls `setOutput("monitoringView", monitoringPayload)` before any other render logic.
**How to avoid:** Remove the `setOutput("monitoringView", ...)` call when the `<pre>` is removed. Replace it with `renderMonitoringPanel(monitoringPayload)`.
**Warning signs:** Console error "Cannot set properties of null (setting 'textContent')".

### Pitfall 3: Null perf_drift When Labels Unavailable
**What goes wrong:** `payload.perf_drift` is null when no labels have been ingested (the current demo state). Accessing `payload.perf_drift.latest_auc` throws.
**Why it happens:** `MonitoringSummaryResponse.perf_drift` is typed `dict | None` and the demo monitoring job produces no labels.
**How to avoid:** Always guard: `if (!payload.perf_drift || payload.perf_drift.latest_auc == null)` before reading AUC fields.
**Warning signs:** "Cannot read properties of null" error on monitoring load.

### Pitfall 4: monitoringNarrative Already Exists — Do Not Duplicate
**What goes wrong:** Developer adds a second narrative element inside the new panel containers.
**Why it happens:** The `<p id="monitoringNarrative">` is already in `index.html` below the refresh button area; easy to miss.
**How to avoid:** Confirm existing element position in `index.html` before adding HTML. The Phase 1 implementation placed this element and it is already wired.
**Warning signs:** Two narrative blocks appear, one empty.

### Pitfall 5: drift_features Object Key Iteration Order
**What goes wrong:** Feature badges appear in non-deterministic order across browsers.
**Why it happens:** JavaScript object key iteration order is insertion order for string keys, which is generally stable but depends on JSON parse order.
**How to avoid:** Use `Object.entries(driftFeatures)` — insertion order is consistent from the Python dict serialization.

## Code Examples

### Full loadMonitoring() After Refactor
```javascript
// Source: existing app.js loadMonitoring() + renderMonitoringPanel() addition
async function loadMonitoring() {
  try {
    const monitoringPayload = await fetch("/monitoring/summary").then(readJson);
    renderMonitoringPanel(monitoringPayload);         // replaces setOutput("monitoringView", ...)
    setNarrative("monitoringNarrative", null);        // clear previous (unchanged)
    if (monitoringPayload.available) {
      fetchNarrative("monitoring", monitoringPayload)
        .then((narrative) => setNarrative("monitoringNarrative", narrative));
    }
  } catch (error) {
    const container = document.getElementById('driftIndicators');
    if (container) container.innerHTML = `<p class="mono error">${error.message}</p>`;
    setNarrative("monitoringNarrative", null);
  }
}
```

### MonitoringSummaryResponse Shape (verified from schemas.py + actual JSON files)
```javascript
// GET /monitoring/summary response structure
{
  available: true,
  summary_markdown: "# Monitoring Summary\n...",
  drift_features: {
    "credit_score": { psi: 0.0, ks_statistic: 0.0, ks_p_value: 1.0, severity: "ok", alert: false },
    "orig_ltv":     { psi: 0.0, ... },
    "orig_dti":     { psi: 0.0, ... },
    "orig_upb":     { psi: 0.0, ... },
    "orig_interest_rate": { psi: 0.0, ... },
    "orig_cltv":    { psi: 0.0, ... }
  },
  score_drift: {
    psi: 0.0, ks_statistic: 0.0, ks_p_value: 1.0,
    reference_percentiles: { p10, p25, p50, p75, p90 },
    current_percentiles:   { p10, p25, p50, p75, p90 },
    mean_shift: 0.0, severity: "ok", alert: false
  },
  perf_drift: null  // null in demo mode — labels not available
}
```

### CSS additions for drift panel
```css
/* Source: existing badge pattern in styles.css, scoped to monitoring */
.drift-badges {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 10px;
}

.drift-feature-badge {
  font-size: 0.78rem;
  padding: 4px 10px;
  cursor: default;
}

.drift-legend {
  margin-bottom: 4px;
}

.drift-key { font-weight: 600; }
.drift-ok   { color: var(--success); }
.drift-warn { color: var(--warning); }
.drift-alert { color: var(--danger); }

#modelAucRow {
  margin-top: 10px;
}
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Raw JSON in `<pre id="monitoringView">` | Structured visual panel | Phase 4 (now) | Visitors understand model health without reading JSON |
| PSI data unused in frontend | Per-feature color badges | Phase 4 (now) | MON-02 satisfied |
| AUC hidden in raw JSON | Prominent AUC + trend label | Phase 4 (now) | MON-03 satisfied |
| Narrative already loads | Narrative displayed below panel | Phase 1 established | MON-04 already functional once panel HTML exists |

**Note:** The AI narrative for monitoring (MON-04 / AI-03) was implemented in Phase 1. The `fetchNarrative("monitoring", ...)` call in `loadMonitoring()` is already wired. The only reason the narrative isn't visible is that `<p id="monitoringNarrative">` is positioned below a `<pre>` that dominates the view. Removing the `<pre>` and building the panel will naturally surface the narrative.

## Open Questions

1. **score_drift display in panel**
   - What we know: `score_drift` data is present in the response (PSI, KS stat, mean shift, severity) but MON-02 only specifies per-feature drift indicators.
   - What's unclear: Should score drift PSI also get an indicator in the panel, or only feature-level drift?
   - Recommendation: Keep Phase 4 strictly to MON-02 scope (feature-level drift badges). Score drift can be shown as a single summary badge if the panel has room; otherwise defer to V2.

2. **"No monitoring data" empty state**
   - What we know: `available=false` when no report files exist on disk (demo before any monitoring job runs).
   - What's unclear: Should the Refresh button be the only call-to-action?
   - Recommendation: Show "No monitoring data yet. Run a monitoring job to see results." inline in `#driftIndicators`. No modal or additional CTA needed.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (existing) |
| Config file | `pyproject.toml` |
| Quick run command | `pytest tests/test_api_contract.py -x -q` |
| Full suite command | `pytest tests/ -x -q` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| MON-01 | `GET /monitoring/summary` returns correct shape; `available` field correct | unit (contract) | `pytest tests/test_api_contract.py::test_monitoring_summary_loads_reports -x` | Already exists |
| MON-01 | `GET /monitoring/summary` returns `available=false` when no files | unit (contract) | `pytest tests/test_api_contract.py::test_monitoring_summary_unavailable -x` | Already exists |
| MON-02 | `getDriftClass()` returns correct CSS class for each PSI range | unit (JS logic via Python contract test) | manual-only — vanilla JS has no test harness; visual verification required | N/A — manual |
| MON-02 | drift badges render for each feature in `drift_features` | smoke | manual visual verification | N/A — manual |
| MON-03 | AUC row shows "Not yet available" when `perf_drift` is null | smoke | manual visual verification | N/A — manual |
| MON-03 | AUC value and trend badge visible when `perf_drift` has data | smoke | manual visual verification | N/A — manual |
| MON-04 | `monitoringNarrative` element shows text when API returns narrative | smoke | manual visual verification (ANTHROPIC_API_KEY required) | N/A — manual |

**Note on JS testing:** This project has no JS test runner (no jest/vitest config found). Frontend logic verification is done through manual visual checks, consistent with prior phases. The contract tests in `test_api_contract.py` cover the backend API contract; frontend rendering is human-verified.

### Sampling Rate
- **Per task commit:** `pytest tests/test_api_contract.py -x -q`
- **Per wave merge:** `pytest tests/ -x -q`
- **Phase gate:** Full suite green + human visual verification before `/gsd:verify-work`

### Wave 0 Gaps
None — existing test infrastructure covers all backend requirements for this phase. Frontend rendering requires human visual verification (no JS test runner in project).

## Sources

### Primary (HIGH confidence)
- `/Users/chivonpowers/predictive-modeling-ai/service/api.py` — `monitoring_summary()` endpoint, `_build_prompt()` monitoring context, full endpoint list
- `/Users/chivonpowers/predictive-modeling-ai/service/schemas.py` — `MonitoringSummaryResponse` shape
- `/Users/chivonpowers/predictive-modeling-ai/monitoring/drift.py` — `PSI_WARN=0.10`, `PSI_ALERT=0.25`, per-feature result schema
- `/Users/chivonpowers/predictive-modeling-ai/monitoring/perf_drift.py` — `run_perf_drift` return schema: `latest_auc`, `trend`, `alert`
- `/Users/chivonpowers/predictive-modeling-ai/service/static/app.js` — all existing render patterns, `loadMonitoring()`, `fetchNarrative()`, `setNarrative()`
- `/Users/chivonpowers/predictive-modeling-ai/service/static/styles.css` — CSS custom properties, `.badge-*` classes, existing layout patterns
- `/Users/chivonpowers/predictive-modeling-ai/service/static/index.html` — current monitoring section DOM structure
- `/Users/chivonpowers/predictive-modeling-ai/reports/monitoring/drift_features.json` — confirmed actual API response shape
- `/Users/chivonpowers/predictive-modeling-ai/reports/monitoring/score_drift.json` — confirmed actual API response shape
- `/Users/chivonpowers/predictive-modeling-ai/tests/test_api_contract.py` — existing monitoring contract tests
- `/Users/chivonpowers/predictive-modeling-ai/.planning/REQUIREMENTS.md` — MON-01 through MON-04 exact specifications

### Secondary (MEDIUM confidence)
- `.planning/STATE.md` — confirmed Phase 1 placed `monitoringNarrative` element and wired `fetchNarrative("monitoring", ...)` in `loadMonitoring()`

### Tertiary (LOW confidence)
None.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all files read directly; no external dependencies needed
- Architecture: HIGH — patterns confirmed from Phase 1–3 code; endpoint contract confirmed from schemas and live JSON
- Pitfalls: HIGH — identified from direct code inspection (threshold mismatch, null perf_drift, stale element reference)

**Research date:** 2026-03-13
**Valid until:** 2026-06-13 (stable; no external dependency changes)

# Phase 2: Score Panel Redesign - Research

**Researched:** 2026-03-12
**Domain:** Vanilla JS SVG visualization, CSS custom properties, DOM manipulation
**Confidence:** HIGH

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- Risk tier thresholds: Low <25% · Moderate 25–50% · High 50–75% · Very High >75%
- Tier badge colors: Low = green, Moderate = yellow/amber, High/Very High = red
- Badge sits inline with gauge (below or beside the arc) — gauge shows number, badge names tier
- Existing threshold input (default 0.5) is for approve/deny only; risk tier uses fixed PD bands
- Raw JSON `<pre id="scoreView">` removed entirely — no collapse/toggle
- Visual components (gauge + badge + factor bars + AI narrative) are the complete replacement
- Show top 5 factors by SHAP magnitude, descending
- Direction via color only: bars extend right in red for risk-increasing (positive SHAP), left in green for risk-reducing (negative SHAP)
- Labels show feature name only — no raw SHAP values or percentages
- Layout: gauge + badge group at top, factor bars below
- Three scenario buttons: Prime Borrower (credit 780/LTV 65/DTI 25), Borderline (credit 700/LTV 85/DTI 40), High Risk (credit 620/LTV 97/DTI 49)
- Clicking pre-fills the JSON textarea; textarea remains editable
- Activate model section left in place untouched for Phase 2

### Claude's Discretion
- Exact SVG arc gauge dimensions and stroke width
- Needle vs filled arc vs segmented arc visual style
- Spacing and typography within the score panel
- Empty/loading state for factor bars when top_factors is empty list
- Gauge animation on score result

### Deferred Ideas (OUT OF SCOPE)
- Removing/hiding the activate model section (Phase 3 decision)
- Feature name friendly labels (e.g. "orig_ltv" → "LTV Ratio") — could be Phase 2 polish or deferred to Phase 4
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| VIZ-01 | Single loan score displays a risk gauge (SVG arc, green→yellow→red) showing PD score value | SVG arc math documented below; CSS custom properties for colors already in codebase |
| VIZ-02 | Single loan score displays factor contribution bars (horizontal, magnitude + direction) for top_factors | Factor data structure confirmed: `Factor { name: str, value: float }`, positive = risk-increasing; bar rendering pattern documented |
| VIZ-03 | Single loan score displays a risk tier badge (Low / Moderate / High / Very High) derived from PD threshold | Tier logic: <0.25/0.25–0.5/0.5–0.75/>0.75; existing `.badge` class extended with color variants |
| VIZ-04 | Raw JSON score output replaced by visual components | `<pre id="scoreView">` removed; `setOutput("scoreView", payload)` call replaced in `initScoreForm()` at line 180 |
| SCEN-01 | Score panel has three pre-built scenario buttons | Buttons added to `scoreForm` in `index.html`; JS handler pre-fills features textarea |
| SCEN-02 | Clicking a scenario populates the features form with preset values | Exact preset values confirmed in CONTEXT.md; textarea `name="features"` is the target |
| SCEN-03 | JSON editor remains editable after scenario population | Textarea stays `contenteditable`; scenario click only sets `.value`, no `readonly` attribute |
</phase_requirements>

---

## Summary

Phase 2 is a pure frontend change — no new backend endpoints, no Python changes. The `/score` API already returns `{ pd: float, decision: string, top_factors: [{ name: string, value: float }] }` and `top_factors` is already populated by the `ModelLoader` via SHAP, linear coefficients, or feature importances (in priority order). The task is to replace the raw JSON `<pre>` output with three new DOM structures: an SVG arc gauge, a risk tier badge, and horizontal factor bars.

All work lives in two files: `service/static/app.js` and `service/static/index.html`, with additions to `service/static/styles.css`. The existing codebase establishes clear patterns: vanilla ES6 with no build step, SVG rendered as `innerHTML` strings (see `renderForecastChart`), and CSS custom properties for all color values. The new components follow these same patterns exactly.

A confirmed codebase gap: there is no feature name friendly-label map anywhere in `features/`, `config/`, or `service/`. Feature names like `orig_ltv`, `orig_dti`, `credit_score` will display as-is. The CONTEXT.md marks this as potentially deferred to Phase 4, so no action is needed in Phase 2.

**Primary recommendation:** Implement all three visual components as vanilla JS render functions that write SVG/HTML into new container `div` elements, following the exact same `innerHTML` pattern used in `renderForecastChart`.

---

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| SVG (inline) | Browser-native | Arc gauge and factor bars | No dependency, renders in all browsers, matches existing forecast chart pattern |
| CSS custom properties | Browser-native | Risk tier color tokens | Already established in styles.css; new vars follow same pattern |
| Vanilla ES6 | Browser-native | All JS logic | Project decision — no framework; matches existing app.js |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `requestAnimationFrame` | Browser-native | Gauge arc animation | If implementing the discretionary gauge animation |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Inline SVG string | D3.js | D3 would add a dependency and build complexity; SVG is sufficient for a static arc |
| CSS-only bars | SVG bars | CSS `width` percentage bars are simpler for horizontal factor bars; SVG is only needed for the circular gauge |

**Installation:** No new packages needed.

---

## Architecture Patterns

### File Change Map
```
service/static/
├── index.html    — remove <pre id="scoreView">, add gauge/badge/bars containers, add scenario buttons
├── app.js        — replace setOutput("scoreView") call, add renderScorePanel(), addScenarioButtons()
└── styles.css    — add --success, --warning CSS vars; add .badge-success, .badge-warning, .badge-danger; add .factor-bar styles
```

### Pattern 1: SVG Arc Gauge (following renderForecastChart style)

**What:** A semicircular arc that fills from 0% to the PD score value. The background arc is grey; the colored arc overlays it. The PD value as a percentage sits centered in the arc.

**SVG arc math:** A semicircle uses `stroke-dasharray` and `stroke-dashoffset` to show partial fill.
- For a semicircle of radius `r`, the circumference of the full circle is `2 * Math.PI * r`
- A semicircle uses only half that: `Math.PI * r`
- To show `pd` (0.0–1.0) fraction: `dasharray = circumference`, `dashoffset = circumference * (1 - pd)`
- The arc path uses `d="M cx-r,cy A r,r 0 0,1 cx+r,cy"` for a top semicircle (180° sweep)

**Color logic:** Single color determined by tier (not gradient). Green below 25%, amber 25–50%, red 50%+.

**Example:**
```javascript
// Source: project pattern — follows renderForecastChart() in app.js
function renderScoreGauge(containerEl, pd) {
  const r = 70;
  const cx = 100;
  const cy = 90;
  const circ = Math.PI * r;
  const dashOffset = circ * (1 - Math.min(1, Math.max(0, pd)));
  const color = pd < 0.25 ? 'var(--success)' : pd < 0.5 ? 'var(--warning)' : 'var(--danger)';
  const pct = Math.round(pd * 100);
  containerEl.innerHTML = `
    <svg viewBox="0 0 200 100" role="img" aria-label="Risk gauge: ${pct}%">
      <path d="M ${cx - r},${cy} A ${r},${r} 0 0,1 ${cx + r},${cy}"
            fill="none" stroke="var(--line)" stroke-width="14" stroke-linecap="round"/>
      <path d="M ${cx - r},${cy} A ${r},${r} 0 0,1 ${cx + r},${cy}"
            fill="none" stroke="${color}" stroke-width="14" stroke-linecap="round"
            stroke-dasharray="${circ.toFixed(2)}" stroke-dashoffset="${dashOffset.toFixed(2)}"/>
      <text x="${cx}" y="${cy - 12}" text-anchor="middle" fill="var(--ink)"
            font-size="26" font-weight="700" font-family="inherit">${pct}%</text>
    </svg>
  `;
}
```

### Pattern 2: Risk Tier Badge (extending existing .badge class)

**What:** Inline colored pill below the gauge.

**Tier logic:**
```javascript
function getRiskTier(pd) {
  if (pd < 0.25) return { label: 'Low', cls: 'badge-success' };
  if (pd < 0.50) return { label: 'Moderate', cls: 'badge-warning' };
  if (pd < 0.75) return { label: 'High', cls: 'badge-danger' };
  return { label: 'Very High', cls: 'badge-danger' };
}
```

**CSS additions needed:**
```css
:root {
  --success: #1a7f37;   /* green — distinct from --accent teal */
  --warning: #9a6700;   /* amber */
}

.badge-success { background: #d3f4df; border-color: #9ee6b5; color: #1a7f37; }
.badge-warning { background: #fef3c7; border-color: #fcd34d; color: #9a6700; }
.badge-danger  { background: #fde8e8; border-color: #fca5a5; color: var(--danger); }
```

### Pattern 3: Factor Contribution Bars (CSS, not SVG)

**What:** Horizontal bars extending left (green) or right (red) from a center dividing line. Top 5 factors by `|value|` magnitude. The API already returns them sorted descending — no re-sort needed at the browser side (confirmed: `_top_factors` sorts by `abs(x[1])` before returning).

**Layout:** Use CSS flexbox. Each row: `[label] [bar-track with center line]`. Bar `width` is proportional to magnitude. Normalize max bar to 100% of half-track width.

```javascript
// Source: project pattern — CSS-based, no SVG needed
function renderFactorBars(containerEl, factors) {
  if (!factors || factors.length === 0) {
    containerEl.innerHTML = '<p class="chart-summary">No factor data available.</p>';
    return;
  }
  const maxAbs = Math.max(...factors.map(f => Math.abs(f.value)), 0.001);
  const rows = factors.map(f => {
    const pct = (Math.abs(f.value) / maxAbs * 50).toFixed(1); // max 50% of track
    const dir = f.value > 0 ? 'right' : 'left';
    const cls = f.value > 0 ? 'bar-risk' : 'bar-safe';
    return `
      <div class="factor-row">
        <span class="factor-label">${f.name}</span>
        <div class="factor-track">
          <div class="factor-bar ${cls} factor-bar--${dir}" style="width:${pct}%"></div>
        </div>
      </div>`;
  }).join('');
  containerEl.innerHTML = `<div class="factor-bars">${rows}</div>`;
}
```

**CSS for factor bars:**
```css
.factor-bars { display: flex; flex-direction: column; gap: 6px; margin-top: 12px; }
.factor-row { display: flex; align-items: center; gap: 8px; }
.factor-label { font-size: 0.8rem; width: 120px; text-align: right; color: var(--ink); flex-shrink: 0; }
.factor-track {
  flex: 1;
  height: 14px;
  background: transparent;
  position: relative;
  display: flex;
  align-items: center;
}
.factor-track::before {
  content: '';
  position: absolute;
  left: 50%;
  top: 0; bottom: 0;
  width: 1px;
  background: var(--line);
}
.factor-bar {
  height: 10px;
  border-radius: 3px;
  position: absolute;
}
.factor-bar--right { left: 50%; background: var(--danger); }
.factor-bar--left  { right: 50%; background: var(--success); }
```

### Pattern 4: Scenario Buttons

**What:** Three buttons above the features textarea that pre-fill the JSON.

**HTML placement:** Inside `#scoreForm`, before the features label.

**JS handler in `initScoreForm()`:**
```javascript
const SCENARIOS = {
  'Prime Borrower':  { credit_score: 780, orig_ltv: 65, orig_dti: 25, orig_upb: 350000, orig_interest_rate: 6.5 },
  'Borderline':      { credit_score: 700, orig_ltv: 85, orig_dti: 40, orig_upb: 350000, orig_interest_rate: 6.5 },
  'High Risk':       { credit_score: 620, orig_ltv: 97, orig_dti: 49, orig_upb: 350000, orig_interest_rate: 7.4 },
};

// Wire scenario buttons
form.querySelectorAll('[data-scenario]').forEach(btn => {
  btn.addEventListener('click', () => {
    form.features.value = pretty(SCENARIOS[btn.dataset.scenario]);
  });
});
```

**HTML for buttons:**
```html
<div class="button-row scenario-row">
  <button type="button" data-scenario="Prime Borrower" class="btn-scenario">Prime Borrower</button>
  <button type="button" data-scenario="Borderline" class="btn-scenario">Borderline</button>
  <button type="button" data-scenario="High Risk" class="btn-scenario">High Risk</button>
</div>
```

### HTML Container Structure to Replace `<pre id="scoreView">`

```html
<!-- replaces: <pre id="scoreView" class="mono">No score yet.</pre> -->
<div id="scorePanel" hidden>
  <div class="score-gauge-wrap">
    <div id="scoreGauge"></div>
    <span id="scoreBadge" class="badge"></span>
  </div>
  <div id="scoreFactors"></div>
</div>
<p id="scoreError" class="mono error" hidden></p>
<p id="scoreNarrative" class="narrative" hidden></p>
```

### Integration Point: `initScoreForm()` Score Handler

**Current code (lines 172–187 of app.js):**
```javascript
const payload = await fetch("/score", ...).then(readJson);
setOutput("scoreView", payload);           // ← REPLACE THIS
setNarrative("scoreNarrative", null);
fetchNarrative("score", payload).then(...);
```

**Replacement:**
```javascript
const payload = await fetch("/score", ...).then(readJson);
renderScorePanel(payload);                 // new function
setNarrative("scoreNarrative", null);
fetchNarrative("score", payload).then(...);
```

**`renderScorePanel(payload)` orchestrates:**
1. `renderScoreGauge(gaugeEl, payload.pd)`
2. `renderRiskBadge(badgeEl, payload.pd)`
3. `renderFactorBars(factorsEl, payload.top_factors)`
4. Show `#scorePanel`, hide `#scoreError`

**Error path replacement:**
```javascript
// catch block: replace setOutput("scoreView", error.message, true)
document.getElementById('scorePanel').hidden = true;
const errEl = document.getElementById('scoreError');
errEl.textContent = error.message;
errEl.hidden = false;
```

### Anti-Patterns to Avoid

- **Importing a charting library:** SVG inline is sufficient and matches existing pattern. D3/Chart.js would require a CDN link or build step.
- **Using a CSS `<progress>` element for bars:** Custom SVG/CSS gives full bidirectional control (left/right from center); `<progress>` is unidirectional.
- **Calculating bar width as raw SHAP value percent:** Normalize to `maxAbs` so the largest bar always fills to max width regardless of absolute SHAP magnitude.
- **Hardcoding hex colors:** All risk colors must use CSS custom properties (`var(--success)`, `var(--warning)`, `var(--danger)`) to stay consistent with the design system.
- **Setting `readonly` on the features textarea after scenario click:** SCEN-03 explicitly requires the textarea remain editable.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| SVG arc gauge percentage fill | Custom trigonometry lookup table | `stroke-dasharray` / `stroke-dashoffset` CSS technique | Native SVG property, one formula, no edge cases |
| Color interpolation across risk spectrum | Custom HSL interpolation | Discrete tier colors at threshold boundaries | Non-technical audience reads colors, not gradients; discrete is clearer |
| Feature name mapping | Custom lookup at render time | Display raw names in Phase 2 (friendly labels deferred) | No label map exists in codebase; deferred to Phase 4 |

**Key insight:** The entire visualization can be built with `innerHTML` string templates and CSS, matching the exact pattern already established by `renderForecastChart`. No additional abstractions are needed.

---

## Common Pitfalls

### Pitfall 1: `top_factors` Empty List on Model Without SHAP
**What goes wrong:** `ModelLoader._top_factors()` returns `[]` silently when SHAP extraction fails and no feature importances are available. Factor bars render as empty or throw on `Math.max(...[])`.
**Why it happens:** `_explainer` is only loaded if `current_explainer.joblib` exists alongside the model; no explainer file = no SHAP.
**How to avoid:** Guard against empty array in `renderFactorBars`: check `factors.length === 0` before computing `maxAbs`; show a graceful empty state message.
**Warning signs:** `Math.max(...[])` returns `-Infinity` and bars render at 0 width or break.

### Pitfall 2: SVG `stroke-dashoffset` Direction
**What goes wrong:** Arc fills backwards (from the wrong end) if `dashoffset` direction is not set correctly.
**Why it happens:** SVG path direction determines which end the offset starts from. The path `M left,cy A r,r 0 0,1 right,cy` draws left-to-right; offset reduces from the end (right side).
**How to avoid:** Verify arc draws from left (0%) to right (100%) by testing with `pd=1.0` (full fill) and `pd=0.0` (empty). The `0 0,1` arc flag means counter-clockwise then sweep=1 (clockwise); adjust if needed.

### Pitfall 3: Scenario Buttons Submit the Form
**What goes wrong:** Clicking scenario buttons triggers form submission and a premature score API call.
**Why it happens:** `<button>` inside a `<form>` defaults to `type="submit"`.
**How to avoid:** Always specify `type="button"` on scenario buttons. Already noted in the HTML pattern above.

### Pitfall 4: `pretty()` Not Available in Scenario Handler
**What goes wrong:** `form.features.value = JSON.stringify(SCENARIOS[name], null, 2)` works but the project already has `pretty()` defined globally in app.js — use it for consistency.
**How to avoid:** Use `pretty(SCENARIOS[btn.dataset.scenario])` in the scenario click handler.

### Pitfall 5: `scorePanel` Hidden State After Error
**What goes wrong:** After an error, `#scorePanel` remains visible from a previous successful score.
**Why it happens:** Error handler only shows `#scoreError` but doesn't hide `#scorePanel`.
**How to avoid:** Error path must explicitly set `scorePanel.hidden = true` and `scoreError.hidden = false`.

---

## Code Examples

### Confirmed API Response Shape (from schemas.py)
```python
# Source: service/schemas.py
class Factor(BaseModel):
    name: str
    value: float  # positive SHAP = increases default risk; negative = reduces

class ScoreResponse(BaseModel):
    pd: float      # 0.0–1.0, predicted probability of default
    decision: str  # 'default' or 'current'
    top_factors: list[Factor]  # already sorted by |value| descending, up to TOP_N_FACTORS (default 5)
```

### Confirmed Existing CSS Custom Properties (from styles.css)
```css
/* Source: service/static/styles.css */
:root {
  --bg: #f5f2e9;
  --paper: #fffcf6;
  --ink: #1e1f23;
  --accent: #006d77;        /* teal */
  --accent-soft: #e0f1f2;
  --danger: #b42318;        /* red — use for High/Very High + risk-increasing bars */
  --line: #d9d2c4;
  --shadow: 0 14px 40px rgba(18, 28, 36, 0.12);
  /* Phase 2 adds: --success, --warning */
}
```

### Confirmed Existing `.badge` Class (from styles.css)
```css
/* Source: service/static/styles.css — extend with color variants */
.badge {
  background: var(--accent-soft);
  border: 1px solid #b8dcdc;
  padding: 6px 10px;
  border-radius: 999px;
  font-size: 0.8rem;
}
```

### `initScoreForm` Location (app.js line 168)
```javascript
// Source: service/static/app.js line 168–188
function initScoreForm() {
  const form = document.getElementById("scoreForm");
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    try {
      const features = JSON.parse(form.features.value);
      const threshold = Number(form.threshold.value);
      const payload = await fetch("/score", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ features, threshold }),
      }).then(readJson);
      setOutput("scoreView", payload);   // ← line 180: replace this
      setNarrative("scoreNarrative", null);
      fetchNarrative("score", payload).then((narrative) => setNarrative("scoreNarrative", narrative));
    } catch (error) {
      setOutput("scoreView", error.message, true);  // ← line 185: replace this
      setNarrative("scoreNarrative", null);
    }
  });
}
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Raw JSON `<pre>` output | SVG gauge + badge + factor bars | Phase 2 (now) | Non-technical visitors can read risk without understanding JSON |
| No scenario entry points | Three pre-built scenario buttons | Phase 2 (now) | Removes need to hand-edit JSON for common demo cases |

**Deprecated/outdated:**
- `<pre id="scoreView" class="mono">`: Removed in this phase. The `setOutput("scoreView", ...)` call is also removed.

---

## Open Questions

1. **Scenario preset `orig_upb` and `orig_interest_rate` values**
   - What we know: CONTEXT.md specifies credit score, LTV, DTI for each scenario but not UPB or interest rate
   - What's unclear: The features textarea currently has `orig_upb: 350000` and `orig_interest_rate: 6.5` as defaults
   - Recommendation: Carry the defaults from the existing textarea for fields not specified in CONTEXT.md. High Risk scenario use slightly higher rate (7.4%) to reflect risk profile.

2. **Gauge animation on score result**
   - What we know: Marked as Claude's discretion in CONTEXT.md
   - What's unclear: CSS `transition` on `stroke-dashoffset` vs. JS-driven `requestAnimationFrame`
   - Recommendation: CSS transition on `stroke-dashoffset` (300ms ease-out) applied via a class toggle after render — simpler and matches `button:hover` transition pattern in styles.css.

---

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 8.2.2 |
| Config file | `pyproject.toml` `[tool.pytest.ini_options]` — testpaths = ["tests"] |
| Quick run command | `pytest tests/test_api_contract.py -v -x` |
| Full suite command | `pytest tests/ -v` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| VIZ-01 | Gauge container present in HTML after score | smoke (HTML string check) | `pytest tests/test_score_panel.py::test_score_panel_html_structure -x` | ❌ Wave 0 |
| VIZ-02 | Factor bars container present after score | smoke (HTML string check) | `pytest tests/test_score_panel.py::test_factor_bars_html_structure -x` | ❌ Wave 0 |
| VIZ-03 | Badge text matches tier for known pd values | unit (JS logic via Python) | `pytest tests/test_score_panel.py::test_risk_tier_thresholds -x` | ❌ Wave 0 |
| VIZ-04 | `scoreView` pre element absent from rendered HTML | smoke (HTML string check) | `pytest tests/test_api_contract.py::test_ui_root_serves_html -x` | ✅ (extend) |
| SCEN-01 | Scenario button elements present in HTML | smoke (HTML string check) | `pytest tests/test_score_panel.py::test_scenario_buttons_present -x` | ❌ Wave 0 |
| SCEN-02 | Preset JSON values match spec | unit (Python dict comparison) | `pytest tests/test_score_panel.py::test_scenario_preset_values -x` | ❌ Wave 0 |
| SCEN-03 | Features textarea has no readonly attribute | smoke (HTML string check) | `pytest tests/test_score_panel.py::test_features_textarea_editable -x` | ❌ Wave 0 |

**Note on test strategy:** The frontend is pure HTML/CSS/JS with no build step. Tests for VIZ-01 through SCEN-03 are best expressed as HTML structure checks against the served `index.html` content (using `TestClient`) plus Python unit tests that encode the risk tier logic and scenario preset values as assertions. Full interactivity testing (scenario button click behavior, gauge fill animation) is manual-only.

### Sampling Rate
- **Per task commit:** `pytest tests/test_api_contract.py tests/test_score_panel.py -v -x`
- **Per wave merge:** `pytest tests/ -v`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_score_panel.py` — covers VIZ-01 through SCEN-03 structural and logic assertions
- [ ] Extend `tests/test_api_contract.py::test_ui_root_serves_html` — assert `scoreView` pre element is absent, assert scenario button data attributes present

*(Existing test infrastructure — pytest + FastAPI TestClient — covers all needs; only new test file is required)*

---

## Sources

### Primary (HIGH confidence)
- Direct codebase read — `service/static/app.js`, `service/static/index.html`, `service/static/styles.css`
- Direct codebase read — `service/schemas.py` (ScoreResponse, Factor schema)
- Direct codebase read — `service/model_loader.py` (confirms `_top_factors` sort order and empty-list failure modes)
- Direct codebase read — `features/feature_defs.py`, `config/features.yaml` (confirms no friendly label map exists)
- Direct codebase read — `pyproject.toml` (confirms pytest 8.2.2, no frontend build step)

### Secondary (MEDIUM confidence)
- SVG `stroke-dasharray` / `stroke-dashoffset` technique: well-established SVG pattern used across the web for progress/gauge indicators; no external source needed beyond SVG spec

### Tertiary (LOW confidence)
- None

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — no new dependencies; all patterns verified directly in codebase
- Architecture: HIGH — exact file/line locations identified; render function signatures defined
- Pitfalls: HIGH — empty `top_factors` failure mode confirmed in `model_loader.py`; button submit default confirmed from HTML spec knowledge

**Research date:** 2026-03-12
**Valid until:** 2026-04-12 (stable — no fast-moving dependencies)

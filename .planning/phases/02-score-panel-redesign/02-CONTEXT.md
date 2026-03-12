# Phase 2: Score Panel Redesign - Context

**Gathered:** 2026-03-12
**Status:** Ready for planning

<domain>
## Phase Boundary

Replace the raw JSON score output with a visual risk panel (SVG arc gauge, risk tier badge, factor contribution bars) and add pre-built scenario buttons to the features form. No new backend endpoints needed — `top_factors` (SHAP values with direction) already comes from the `/score` API response. The activate model section and other UI cards are out of scope.

</domain>

<decisions>
## Implementation Decisions

### Risk Tier Thresholds
- Standard PD quartile bands: Low <25% · Moderate 25–50% · High 50–75% · Very High >75%
- Tier badge colors match the gauge: Low = green, Moderate = yellow/amber, High/Very High = red
- Badge sits inline with the gauge (below or beside the arc) — gauge shows the number, badge names the tier
- The existing threshold input (default 0.5) is for approve/deny decision only; risk tier uses fixed PD bands above

### Raw JSON Removal (VIZ-04)
- Remove the raw JSON `<pre id="scoreView">` entirely — no collapse/toggle
- The visual components (gauge + badge + factor bars + AI narrative) are the complete replacement

### Factor Bars
- Show top 5 factors (by SHAP magnitude, descending)
- Direction via color only: bars extend right in red for risk-increasing factors (positive SHAP), left in green for risk-reducing (negative SHAP)
- Labels show feature name only — no raw SHAP values or percentages (non-technical audience)
- Layout: gauge + badge group at top, factor bars below — hierarchy reads as "what's the risk → why"

### Scenario Buttons
- Three buttons: Prime Borrower, Borderline, High Risk
- Preset values per SCEN-02: Prime (credit 780 / LTV 65 / DTI 25), Borderline (credit 700 / LTV 85 / DTI 40), High Risk (credit 620 / LTV 97 / DTI 49)
- Clicking pre-fills the JSON textarea; textarea remains editable (scenarios are starting points)

### Activate Model Section
- Leave in place for Phase 2 — untouched
- Phase 3's demo flow will make it functionally optional for non-technical visitors

### Claude's Discretion
- Exact SVG arc gauge dimensions and stroke width
- Needle vs filled arc vs segmented arc visual style
- Spacing and typography within the score panel
- Empty/loading state for factor bars when top_factors is empty list
- Gauge animation on score result

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- `.badge` class: pill-shaped, accent-soft background, border-radius 999px — extend with color variants for risk tiers (green/amber/red)
- `.card` and `.stack` classes: score panel lives inside an existing card; new visual elements drop into the same structure
- `fetchNarrative()` / `setNarrative()`: already wired to `scoreNarrative` — no changes needed
- CSS custom properties: `--accent` (#006d77 teal), `--accent-soft`, `--danger` (#b42318 red), `--ink`, `--paper` — use these for gauge and bar colors; add `--success` and `--warning` for green/amber

### Established Patterns
- Vanilla ES6, no framework — all new JS goes in `app.js`
- `setOutput(id, data, isError)` pattern for rendering results — factor bars replace this call for score results
- CSS custom properties for all colors — new risk colors should follow the same pattern
- `top_factors` field in `ScoreResponse`: `Factor { name: str, value: float }` where positive SHAP = increases default risk

### Integration Points
- Score handler in `app.js` (~line 169): currently calls `setOutput("scoreView", payload)` — this call gets replaced with gauge/badge/bars rendering
- `#scoreView` pre element in `index.html` (~line 105): removed, replaced with gauge container, badge, and factor bars
- `scoreNarrative` paragraph already present and wired — stays in place below factor bars
- Scenario buttons added to `scoreForm` in `index.html` (~line 90)

</code_context>

<specifics>
## Specific Ideas

- Factor bars visual reference: bars extend from a center line, red rightward for risk-increasing, green leftward for risk-reducing (like a waterfall/tornado chart simplified for vanilla SVG or CSS)
- The demo audience goal is "no ML background required" — feature names like `orig_ltv` may need friendlier labels (e.g. "LTV Ratio") — researcher should check if a label map exists in the codebase

</specifics>

<deferred>
## Deferred Ideas

- Removing/hiding the activate model section — Phase 3 decision after demo flow is built
- Feature name friendly labels (e.g. "orig_ltv" → "LTV Ratio") — could be a polish item in Phase 2 or deferred to Phase 4

</deferred>

---

*Phase: 02-score-panel-redesign*
*Context gathered: 2026-03-12*

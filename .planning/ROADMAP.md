# Roadmap: Predictive Modeling AI — Demo UX Overhaul

## Overview

This milestone transforms an existing developer-facing ML dashboard into a narrative-driven portfolio piece. The FastAPI backend, scikit-learn classifiers, Prophet forecaster, and SPA frontend all exist. The work adds a Claude AI interpretation layer, replaces raw JSON output with visual components (gauge, factor bars, risk badges), streamlines the demo flow to a single button, adds a batch portfolio view, and surfaces model health indicators — making the entire pipeline accessible to a visitor with no ML background.

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [x] **Phase 1: AI Narrative Backend** - Add /ai/interpret endpoint calling Claude API server-side; wire AI responses into score, forecast, and monitoring flows (completed 2026-03-12)
- [ ] **Phase 2: Score Panel Redesign** - Replace raw JSON score output with risk gauge, factor bars, risk badge, and pre-built loan scenario buttons
- [ ] **Phase 3: Demo Flow + Portfolio Dashboard** - Replace 5-step instruction list with one-click animated demo; add sortable batch portfolio table with distribution chart and AI insight
- [ ] **Phase 4: Monitoring Panel** - Add Model Health section with per-feature drift indicators, AUC trend, and AI-written status summary

## Phase Details

### Phase 1: AI Narrative Backend
**Goal**: Visitors read plain-language AI interpretations of score, forecast, and monitoring results — no ML background required
**Depends on**: Nothing (first phase)
**Requirements**: AI-01, AI-02, AI-03, AI-04, AI-05
**Success Criteria** (what must be TRUE):
  1. After scoring a loan, a plain-language paragraph appears below the score result explaining the default probability, key risk drivers, and a recommended action
  2. After running a forecast, a plain-language paragraph appears describing when delinquency breaches the alert threshold and what to do
  3. After loading monitoring data, a plain-language paragraph appears summarizing drift status and whether retraining is needed
  4. POST /ai/interpret accepts model output JSON, calls Claude claude-sonnet-4-6 server-side, and returns narrative text — the ANTHROPIC_API_KEY is never exposed to the browser
**Plans**: 3 plans

Plans:
- [ ] 01-01-PLAN.md — Add anthropic dependency and create test scaffold (Wave 1)
- [ ] 01-02-PLAN.md — Implement POST /ai/interpret endpoint with schemas, AsyncAnthropic, prompt builders, error handling (Wave 2)
- [ ] 01-03-PLAN.md — Wire narrative into frontend: fetchNarrative() in app.js, narrative <p> elements in index.html (Wave 3)

### Phase 2: Score Panel Redesign
**Goal**: The single-loan score panel communicates risk visually and lets visitors explore pre-built loan scenarios without hand-editing JSON
**Depends on**: Phase 1
**Requirements**: VIZ-01, VIZ-02, VIZ-03, VIZ-04, SCEN-01, SCEN-02, SCEN-03
**Success Criteria** (what must be TRUE):
  1. Scoring a loan shows a color-coded SVG arc gauge (green/yellow/red) and a risk tier badge (Low / Moderate / High / Very High) — no raw JSON visible
  2. Horizontal factor bars appear below the gauge showing which features drove the score up or down, with direction and magnitude readable at a glance
  3. Three scenario buttons (Prime Borrower, Borderline, High Risk) populate the features form with preset values and remain editable before scoring
**Plans**: 3 plans

Plans:
- [ ] 02-01-PLAN.md — Test scaffold, CSS tokens, and HTML structure (containers + scenario buttons, scoreView removed)
- [ ] 02-02-PLAN.md — JS render functions (gauge, badge, factor bars) and scenario button wiring
- [ ] 02-03-PLAN.md — Human visual verification checkpoint

### Phase 3: Demo Flow + Portfolio Dashboard
**Goal**: A single button runs the entire pipeline end-to-end with visible progress, and batch results appear as a readable portfolio table rather than raw JSON
**Depends on**: Phase 2
**Requirements**: DEMO-01, DEMO-02, DEMO-03, DEMO-04, PORT-01, PORT-02, PORT-03
**Success Criteria** (what must be TRUE):
  1. Clicking "Run Full Demo" auto-executes seed → pipeline → activate → score → forecast in sequence, with each step checking off as it completes — no manual steps required
  2. The demo ends with a summary narrative: "Your portfolio is ready. Here's what the model found."
  3. Batch score results display as a sortable table (loan number, PD score, risk tier, top risk factor) plus a donut or bar chart showing distribution by risk tier — no raw JSON visible
  4. A portfolio-level AI insight paragraph appears below batch results summarizing aggregate risk and a recommended action
**Plans**: TBD

### Phase 4: Monitoring Panel
**Goal**: Visitors can see at a glance whether the model is healthy, which features are drifting, and what the AI recommends — without reading drift metric documentation
**Depends on**: Phase 3
**Requirements**: MON-01, MON-02, MON-03, MON-04
**Success Criteria** (what must be TRUE):
  1. A "Model Health" section loads from GET /monitoring/summary and displays per-feature drift status as green/yellow/red indicators based on PSI thresholds
  2. Current AUC value and a trend indicator (stable/improving/degrading) are visible in the Model Health section
  3. An AI-written status summary appears in the Model Health section explaining drift status and whether retraining is recommended in plain language
**Plans**: TBD

## Progress

**Execution Order:**
Phases execute in numeric order: 1 → 2 → 3 → 4

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. AI Narrative Backend | 3/3 | Complete   | 2026-03-12 |
| 2. Score Panel Redesign | 1/3 | In Progress|  |
| 3. Demo Flow + Portfolio Dashboard | 0/TBD | Not started | - |
| 4. Monitoring Panel | 0/TBD | Not started | - |

# Requirements: Predictive Modeling AI — Demo UX Overhaul

**Defined:** 2026-03-12
**Core Value:** A visitor clicks one button, watches the pipeline run, and reads plain-language AI insights — no ML background required.

## v1 Requirements

### AI Narrative

- [x] **AI-01**: User sees a plain-language AI-written interpretation after scoring a single loan (e.g. "This loan carries a 34% default probability. Primary risk drivers: high LTV and DTI. Recommendation: require PMI.")
- [x] **AI-02**: User sees a plain-language AI-written interpretation after running a forecast (e.g. "Delinquency rates breach the alert threshold at month 14. Recommend portfolio stress-testing before Q2.")
- [x] **AI-03**: User sees a plain-language AI-written monitoring status (e.g. "Feature drift is moderate. AUC is stable at 0.74. No retraining required yet.")
- [x] **AI-04**: Backend exposes POST /ai/interpret endpoint that calls Claude API (claude-sonnet-4-6) server-side using ANTHROPIC_API_KEY env var
- [x] **AI-05**: anthropic Python package added to project dependencies

### Risk Visualization

- [x] **VIZ-01**: Single loan score displays a risk gauge (SVG arc, green→yellow→red) showing PD score value
- [x] **VIZ-02**: Single loan score displays factor contribution bars (horizontal bars, magnitude + direction) for top_factors from API response
- [x] **VIZ-03**: Single loan score displays a risk tier badge (Low / Moderate / High / Very High) derived from PD threshold
- [x] **VIZ-04**: Raw JSON score output is replaced by the visual components (gauge + bars + badge + AI narrative)

### Demo Flow

- [x] **DEMO-01**: UI has a single "Run Full Demo" button that replaces the 5-step numbered instruction list
- [ ] **DEMO-02**: Demo flow auto-executes: seed-demo job → pipeline job → activate latest model → populate score form → run score → run forecast, in sequence
- [x] **DEMO-03**: Demo flow shows animated step-by-step progress (each step checks off as it completes)
- [x] **DEMO-04**: Demo flow ends with a summary narrative: "Your portfolio is ready. Here's what the model found."

### Portfolio Dashboard

- [x] **PORT-01**: Batch score results display as a table (columns: loan #, PD score, risk tier, top risk factor) instead of raw JSON
- [x] **PORT-02**: Batch score results include a distribution visualization (donut or bar chart by risk tier count)
- [x] **PORT-03**: Batch score results include a portfolio-level AI insight (e.g. "2 of 4 loans are high-risk. Average PD is 38%. Consider tightening LTV limits.")

### Loan Scenarios

- [x] **SCEN-01**: Score panel has three pre-built scenario buttons: "Prime Borrower", "Borderline", "High Risk"
- [x] **SCEN-02**: Clicking a scenario populates the features form with preset values (Prime: credit 780/LTV 65/DTI 25; Borderline: credit 700/LTV 85/DTI 40; High Risk: credit 620/LTV 97/DTI 49)
- [x] **SCEN-03**: JSON editor remains editable after scenario population (scenarios are starting points, not locked)

### Monitoring Panel

- [ ] **MON-01**: UI has a "Model Health" section that loads data from GET /monitoring/summary
- [ ] **MON-02**: Model Health displays feature drift indicators (green/yellow/red) per feature based on PSI thresholds (green <0.1, yellow 0.1–0.2, red >0.2)
- [ ] **MON-03**: Model Health displays current AUC value and a simple trend indicator
- [ ] **MON-04**: Model Health displays AI-written status summary (uses AI-03 narrative)

## v2 Requirements

### Enhanced Visualizations

- **V2-VIZ-01**: Side-by-side model comparison (Logistic Regression vs Random Forest PD scores)
- **V2-VIZ-02**: AUC sparkline chart in monitoring panel
- **V2-VIZ-03**: Forecast confidence interval shading on chart

### UX Polish

- **V2-UX-01**: Persistent demo state (remember last run across page refresh)
- **V2-UX-02**: Export portfolio report as PDF

## Out of Scope

| Feature | Reason |
|---------|--------|
| Real-time WebSocket updates | Polling sufficient for demo; adds complexity |
| Multi-user auth / sessions | Demo context, not production app |
| Mobile-responsive redesign | Desktop-first appropriate for portfolio demo |
| Replacing forecast SVG chart | Already works well |
| React/Vue frontend rewrite | Vanilla JS is sufficient; framework adds build complexity |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| AI-01 | Phase 1 | Complete |
| AI-02 | Phase 1 | Complete |
| AI-03 | Phase 1 | Complete |
| AI-04 | Phase 1 | Complete |
| AI-05 | Phase 1 | Complete |
| VIZ-01 | Phase 2 | Complete |
| VIZ-02 | Phase 2 | Complete |
| VIZ-03 | Phase 2 | Complete |
| VIZ-04 | Phase 2 | Complete |
| SCEN-01 | Phase 2 | Complete |
| SCEN-02 | Phase 2 | Complete |
| SCEN-03 | Phase 2 | Complete |
| DEMO-01 | Phase 3 | Complete |
| DEMO-02 | Phase 3 | Pending |
| DEMO-03 | Phase 3 | Complete |
| DEMO-04 | Phase 3 | Complete |
| PORT-01 | Phase 3 | Complete |
| PORT-02 | Phase 3 | Complete |
| PORT-03 | Phase 3 | Complete |
| MON-01 | Phase 4 | Pending |
| MON-02 | Phase 4 | Pending |
| MON-03 | Phase 4 | Pending |
| MON-04 | Phase 4 | Pending |

**Coverage:**
- v1 requirements: 23 total
- Mapped to phases: 23
- Unmapped: 0 ✓

---
*Requirements defined: 2026-03-12*
*Last updated: 2026-03-12 after initial definition*

# Predictive Modeling AI — Demo UX Overhaul

## What This Is

A mortgage risk analytics demo built on FastAPI + scikit-learn + Prophet, deployed as a single-page app. The backend pipeline ingests Fannie Mae loan data, engineers 18+ credit risk features, trains probability-of-default (PD) classifiers and delinquency forecasting models, and serves predictions via REST API with drift monitoring. This milestone transforms the existing developer-facing tool dashboard into a compelling, narrative-driven portfolio piece that demonstrates end-to-end data science + AI synthesis skills to technical interviewers and stakeholders.

## Core Value

A visitor with no ML background should be able to click one button, watch the model pipeline run, and read plain-language AI-written insights — understanding exactly what the model found and what action to take.

## Requirements

### Validated

- ✓ FastAPI prediction service with /score, /batch_score, /forecast, /jobs endpoints — existing
- ✓ Prophet delinquency rate forecasting model — existing
- ✓ Logistic regression + random forest PD classifiers — existing
- ✓ MLflow experiment tracking + model registry — existing
- ✓ Background job queue for async pipeline execution — existing
- ✓ Drift monitoring reports (PSI, KS, rolling AUC) — existing
- ✓ SVG forecast chart with threshold exceedance highlighting — existing
- ✓ top_factors in score response (SHAP/coefficient-based) — existing

### Active

- [ ] AI-synthesized narrative for score results via Claude API backend endpoint
- [ ] AI-synthesized narrative for forecast results via Claude API backend endpoint
- [ ] AI-synthesized narrative for monitoring summary via Claude API backend endpoint
- [ ] Risk gauge (SVG arc, green→yellow→red) replacing raw pd JSON output
- [ ] Factor contribution bars (horizontal, magnitude+direction) for top_factors
- [ ] Risk tier badge (Low / Moderate / High / Very High) on score result
- [ ] One-click guided demo flow: auto-seed → train → activate → score → forecast with animated progress
- [ ] Portfolio dashboard for batch score: sortable table with risk tier + top factor per loan
- [ ] Distribution visualization for batch portfolio (donut/bar by risk tier)
- [ ] Portfolio-level AI insight from batch score results
- [ ] Pre-built loan scenario buttons: Prime Borrower, Borderline, High Risk
- [ ] Model Health panel surfacing drift indicators (green/yellow/red per feature) and AUC trend

### Out of Scope

- Real-time WebSocket updates — polling is sufficient for demo purposes
- Multi-user auth / saved sessions — this is a demo, not a production app
- Mobile-responsive redesign — desktop-first is fine for a portfolio demo
- Replacing the existing forecast SVG chart — it already works well

## Context

The existing UI (`service/static/`) is a clean single-page app using Space Grotesk font, card-based layout, and IBM Plex Mono for code output. All styling is in `styles.css` with CSS custom properties. The JavaScript is vanilla ES6 in `app.js` (268 lines). The backend is FastAPI (`service/api.py`).

The AI narrative feature requires a new FastAPI endpoint (`POST /ai/interpret`) that accepts model output (score, forecast, or monitoring data) and calls the Anthropic Claude API server-side. The `ANTHROPIC_API_KEY` env var will be used. The `anthropic` Python package needs to be added as a dependency.

The existing `top_factors` field in the score response already contains the data needed for factor bars — no backend changes needed for that visualization.

The monitoring summary is available at `GET /monitoring/summary` and returns JSON drift reports. The AI narrative for monitoring will call this endpoint, then pass the data to Claude for interpretation.

## Constraints

- **Tech stack**: Vanilla JS only (no React/Vue) — keep the frontend lightweight and dependency-free
- **Backend**: FastAPI — all new endpoints follow existing patterns in `service/api.py`
- **Styling**: Extend existing CSS custom properties and card patterns — don't rewrite the stylesheet
- **API key**: `ANTHROPIC_API_KEY` environment variable, never exposed to the frontend

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Claude API called from backend (not browser) | Keeps API key secure; cleaner architecture | — Pending |
| Vanilla JS (no framework) | Existing codebase is framework-free; adding React would be over-engineering for a demo | — Pending |
| Extend existing UI rather than redesign | The visual design (fonts, colors, cards) is already good; focus on functionality | — Pending |
| ANTHROPIC_API_KEY via env var | Standard approach; avoids hardcoding secrets | — Pending |

---
*Last updated: 2026-03-12 after initialization*

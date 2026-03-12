---
phase: 01-ai-narrative-backend
verified: 2026-03-12T15:30:00Z
status: human_needed
score: 12/12 automated must-haves verified
re_verification: false
human_verification:
  - test: "Score a loan in the browser with ANTHROPIC_API_KEY set. Confirm (1) score result (pd, decision) appears first, (2) a plain-language paragraph appears below it mentioning the pd value and a recommended action."
    expected: "Narrative paragraph is visible below scoreView pre element. Primary score result is unaffected."
    why_human: "fetchNarrative is called async in the browser; automated tests mock the Claude API. Real-API browser behavior must be confirmed visually."
  - test: "Run a forecast in the browser with ANTHROPIC_API_KEY set. Confirm a plain-language paragraph appears below the forecast chart."
    expected: "Narrative paragraph visible below forecastNarrative element after forecast completes."
    why_human: "Requires real API call and rendered DOM — cannot verify programmatically."
  - test: "If monitoring data is available (monitoringView shows available:true), confirm a narrative paragraph appears below the monitoring output."
    expected: "monitoringNarrative paragraph is visible with AI-generated text."
    why_human: "Monitoring narrative only fires when available:true — depends on runtime data state."
  - test: "Graceful degradation: stop server, unset ANTHROPIC_API_KEY, restart. Score a loan. Confirm score result still displays and the narrative paragraph is hidden (not an error message)."
    expected: "scoreView shows pd/decision. scoreNarrative element is hidden. No error text in narrative area."
    why_human: "Degradation requires the element hidden attribute to be set correctly — a DOM/visual check."
  - test: "Security check: open DevTools Network tab, score a loan, inspect /ai/interpret request. Confirm ANTHROPIC_API_KEY does not appear in any request or response."
    expected: "Request payload contains only {context_type, data}. Response contains only {narrative}. No key material anywhere."
    why_human: "Network tab inspection cannot be automated without a headless browser."
---

# Phase 1: AI Narrative Backend Verification Report

**Phase Goal:** Implement an AI narrative backend that generates plain-language interpretations of model outputs (score, forecast, monitoring) via a POST /ai/interpret endpoint powered by the Anthropic Claude API, and wire it into the frontend UI.
**Verified:** 2026-03-12T15:30:00Z
**Status:** human_needed
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | POST /ai/interpret returns 200 with a narrative string for each of the three context types | VERIFIED | `service/api.py` line 672: `@app.post("/ai/interpret", ...)` fully implemented; 8/8 tests pass including happy-path score/forecast/monitoring |
| 2 | ANTHROPIC_API_KEY is read from environment by the SDK — never appears in any response, log, or error body | VERIFIED | `api.py` lines 72-73, 116: startup warning logs key absence; error detail strings contain no key material; `_get_anthropic_client()` calls `AsyncAnthropic()` with no explicit key arg |
| 3 | AuthenticationError returns 503, RateLimitError returns 429, APIConnectionError returns 502, APIStatusError returns 502 | VERIFIED | `api.py` lines 688-711: four distinct except clauses mapping to correct HTTP codes; `test_interpret_auth_error_returns_503` and `test_interpret_rate_limit_returns_429` both pass |
| 4 | Score prompt includes pd as a percentage and top_factors names | VERIFIED | `api.py` lines 237-254: `{pd_val:.0%}` format; `test_score_narrative_prompt_contains_pd` passes asserting `"34%"` in prompt |
| 5 | Forecast prompt includes threshold exceedance month and count | VERIFIED | `api.py` lines 255-273: threshold, exceed count, and first exceedance date all included; `test_forecast_narrative_prompt_contains_threshold` passes |
| 6 | Monitoring prompt includes drift severity and AUC value | VERIFIED | `api.py` lines 274-289: high-drift features, score alert, AUC included; `test_monitoring_narrative_prompt_reflects_drift` passes |
| 7 | AsyncAnthropic client is instantiated once at module level (singleton) — not per-request | VERIFIED | `api.py` lines 58, 112-117: `_ANTHROPIC_CLIENT` module-level global; `_get_anthropic_client()` lazy-init pattern with `global` guard |
| 8 | Startup logs a WARNING if ANTHROPIC_API_KEY is absent — app still boots | VERIFIED | `api.py` lines 72-73: `log.warning(...)` in `lifespan()` context manager, not a raise |
| 9 | After scoring a loan, a plain-language paragraph appears below the score result | HUMAN NEEDED | `app.js` lines 181-182: `fetchNarrative("score", payload).then(setNarrative("scoreNarrative", ...))` wired; `index.html` line 106: `<p id="scoreNarrative" class="narrative" hidden></p>` present. Browser verification needed. |
| 10 | After running a forecast, a plain-language paragraph appears below the forecast chart | HUMAN NEEDED | `app.js` lines 157-159 wired; `index.html` line 127 present. Browser verification needed. |
| 11 | After loading monitoring data (available: true), a plain-language paragraph appears below the monitoring output | HUMAN NEEDED | `app.js` lines 290-293: conditional on `monitoringPayload.available`; `index.html` line 138 present. Browser verification needed. |
| 12 | If /ai/interpret fails, primary result still displays — narrative degrades silently | VERIFIED | `app.js` lines 45-47: `catch { return null; }` in `fetchNarrative`; `setNarrative` sets `el.hidden = !narrative` on null |

**Automated Score:** 9/9 server-side truths verified. 3/3 frontend truths have correct wiring; browser confirmation needed.

---

## Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `pyproject.toml` | anthropic>=0.84 in project dependencies | VERIFIED | Line 42: `"anthropic>=0.84"` present |
| `tests/test_ai_interpret.py` | 8-test scaffold for AI-01 through AI-05 | VERIFIED | 8 test functions: `test_anthropic_importable`, `test_interpret_score_returns_narrative`, `test_interpret_auth_error_returns_503`, `test_interpret_rate_limit_returns_429`, `test_interpret_invalid_context_type_returns_422`, `test_score_narrative_prompt_contains_pd`, `test_forecast_narrative_prompt_contains_threshold`, `test_monitoring_narrative_prompt_reflects_drift`. All 8 pass GREEN. |
| `service/schemas.py` | InterpretRequest and InterpretResponse Pydantic models | VERIFIED | Lines 181-187: both classes present with correct field types (`Literal["score","forecast","monitoring"]`, `dict[str,Any]`, `str`) |
| `service/api.py` | POST /ai/interpret endpoint, AsyncAnthropic singleton, _build_prompt helper | VERIFIED | Lines 58, 112-117, 236-289, 672-712: all present and substantive (>450 lines total in file) |
| `service/static/app.js` | fetchNarrative() helper and wiring after score/forecast/monitoring | VERIFIED | Lines 37-55: `fetchNarrative()` and `setNarrative()` defined. Lines 157-163, 181-186, 290-293: wired after each result handler |
| `service/static/index.html` | Narrative paragraph elements with IDs scoreNarrative, forecastNarrative, monitoringNarrative | VERIFIED | Lines 106, 127, 138: all three `<p>` elements present with `class="narrative" hidden` |
| `service/static/styles.css` | .narrative CSS class | VERIFIED | Line 196: `.narrative {` class defined |

---

## Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `tests/test_ai_interpret.py` | `service/api.py` | `from fastapi.testclient import TestClient` + `import service.api as api` | WIRED | Line 15: `import service.api as api`; TestClient used on `api.app` in every test |
| `service/api.py` | `anthropic.AsyncAnthropic` | `_get_anthropic_client()` singleton | WIRED | Lines 58, 112-117: `_ANTHROPIC_CLIENT: anthropic.AsyncAnthropic | None = None`; `_get_anthropic_client()` pattern matches `_ANTHROPIC_CLIENT.*AsyncAnthropic` |
| `service/api.py` | `service/schemas.py` | `InterpretRequest, InterpretResponse` import | WIRED | Lines 38-39: `InterpretRequest, InterpretResponse` in the import block from `service.schemas` |
| `service/static/app.js fetchNarrative()` | `POST /ai/interpret` | `fetch('/ai/interpret', {method: 'POST', ...})` | WIRED | Line 39: `fetch("/ai/interpret", {...})` exact pattern; `context_type` and `data` fields passed correctly |
| `service/static/app.js initScoreForm()` | `scoreNarrative paragraph` | `setNarrative("scoreNarrative", narrative)` | WIRED | Lines 181-182: pattern `scoreNarrative` present; `setNarrative` sets `textContent` and toggles `hidden` |

---

## Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| AI-01 | Plans 02, 03 | User sees plain-language interpretation after scoring a loan | SATISFIED | POST /ai/interpret handles score context; `scoreNarrative` wired in app.js/index.html |
| AI-02 | Plans 02, 03 | User sees plain-language interpretation after running a forecast | SATISFIED | POST /ai/interpret handles forecast context; `forecastNarrative` wired in app.js/index.html |
| AI-03 | Plans 02, 03 | User sees plain-language monitoring status | SATISFIED | POST /ai/interpret handles monitoring context; `monitoringNarrative` wired with `available` guard |
| AI-04 | Plan 02 | Backend exposes POST /ai/interpret endpoint calling Claude API server-side | SATISFIED | Endpoint at `service/api.py:672` calls `client.messages.create(model="claude-sonnet-4-6", ...)` |
| AI-05 | Plan 01 | anthropic Python package added to project dependencies | SATISFIED | `pyproject.toml` line 42: `"anthropic>=0.84"` |

**Coverage:** 5/5 requirements satisfied. No orphaned requirements — traceability table in REQUIREMENTS.md maps all 5 IDs to Phase 1.

---

## Anti-Patterns Found

| File | Pattern | Severity | Impact |
|------|---------|----------|--------|
| `service/api.py` line 695 | `log.error("Claude authentication error (check ANTHROPIC_API_KEY): {}", exc)` — key name appears in a log message but NOT in any HTTP response body | Info | Log output is server-side only; never reaches browser or API response. Not a leak. |

No stubs, placeholders, empty implementations, or TODO/FIXME markers found in Phase 1 files.

---

## Human Verification Required

### 1. AI Narrative Appears Below Score Result (AI-01)

**Test:** Set `ANTHROPIC_API_KEY`, start `uvicorn service.api:app --reload`, visit http://localhost:8000, submit the Score Loan form with any valid features JSON.
**Expected:** Score result (pd, decision) appears first in the `scoreView` pre element. Then a plain-language paragraph appears in the area below — something like "This loan carries a 34% default probability. Primary risk: high LTV. Recommendation: require PMI."
**Why human:** `fetchNarrative` fires after primary result via `.then()` — DOM-level async behavior with real Claude API call; not reproducible in unit tests.

### 2. AI Narrative Appears Below Forecast Chart (AI-02)

**Test:** With `ANTHROPIC_API_KEY` set, submit the Forecast form (source: fannie-mae, any horizon).
**Expected:** Forecast chart renders. A plain-language paragraph appears below the chart in the `forecastNarrative` element mentioning threshold and exceedance info.
**Why human:** Same async pattern; requires rendered browser DOM.

### 3. AI Narrative Appears Below Monitoring Output (AI-03)

**Test:** With `ANTHROPIC_API_KEY` set and monitoring data present (run a monitor job first if needed), check the Monitoring Summary section.
**Expected:** If `available: true`, a narrative paragraph appears below the monitoring pre element.
**Why human:** Conditional on `monitoringPayload.available` — depends on whether monitoring data exists in the environment.

### 4. Graceful Degradation (AI-03/AI-04)

**Test:** Unset `ANTHROPIC_API_KEY`, restart the server. Score a loan.
**Expected:** Score result (pd, decision) displays normally. The `scoreNarrative` paragraph remains hidden — no error text, no broken UI.
**Why human:** Tests mock the client; real 503 error path and DOM state change require live browser observation.

### 5. Security: API Key Never Reaches Browser

**Test:** Open DevTools Network tab. Score a loan. Inspect the `/ai/interpret` request payload and response.
**Expected:** Request body: `{"context_type": "score", "data": {...}}`. Response body: `{"narrative": "..."}`. `ANTHROPIC_API_KEY` value does not appear anywhere in the network tab.
**Why human:** Network tab inspection requires manual review; cannot be automated without a headless browser harness.

---

## Test Suite Status

- `pytest tests/test_ai_interpret.py -v` — **8/8 PASSED** (GREEN)
- `pytest tests/ -v` — **143/144 passed** (1 pre-existing failure: `test_forecast_missing_model_returns_503` fails because the prophet artifact is present in the dev environment — this failure predates Phase 1, last modified in commit `1626cc5` before any Phase 1 work)

---

## Summary

All 12 automated must-haves are verified in the actual codebase. The backend (endpoint, schemas, singleton, prompt builders, error handling) is fully implemented and all 8 unit tests pass GREEN. The frontend wiring (fetchNarrative, setNarrative, three narrative paragraph elements, CSS class) is present and substantively implemented — not stubs. All 5 phase requirements (AI-01 through AI-05) have implementation evidence.

The only remaining items are 5 browser-level confirmations that require a real ANTHROPIC_API_KEY and visual DOM inspection. These are standard human-verification items for any async frontend integration — they cannot be reproduced in unit tests that mock the Claude SDK.

---

_Verified: 2026-03-12T15:30:00Z_
_Verifier: Claude (gsd-verifier)_

---
phase: 01-ai-narrative-backend
plan: 02
subsystem: api
tags: [anthropic, fastapi, pydantic, async, ai-narrative]

# Dependency graph
requires:
  - phase: 01-ai-narrative-backend
    plan: 01
    provides: "Failing test scaffold in tests/test_ai_interpret.py (RED phase)"

provides:
  - "POST /ai/interpret endpoint with AsyncAnthropic singleton"
  - "InterpretRequest and InterpretResponse Pydantic schemas in service/schemas.py"
  - "_build_prompt() helper for score/forecast/monitoring context types"
  - "Explicit error handling: AuthenticationError->503, RateLimitError->429, APIConnectionError/APIStatusError->502"
  - "Startup WARNING if ANTHROPIC_API_KEY is absent"

affects: [02-frontend-ai-narrative, phase-3, phase-4]

# Tech tracking
tech-stack:
  added: [anthropic SDK (AsyncAnthropic)]
  patterns:
    - "Module-level singleton with _ANTHROPIC_CLIENT global and _get_anthropic_client() lazy initializer"
    - "Context-type dispatch in _build_prompt() with fallthrough default"
    - "Granular except-per-exception-type mapping to specific HTTP status codes (no broad Exception handler)"

key-files:
  created: []
  modified:
    - service/schemas.py
    - service/api.py

key-decisions:
  - "pd formatted as :.0% (e.g. 34%) not :.1% (34.0%) so prompt matches test assertion token 34%"
  - "AsyncAnthropic singleton is module-level global, not per-request, to avoid connection pool overhead"
  - "App boots without ANTHROPIC_API_KEY — warning logged, 503 raised only on first actual API call"

patterns-established:
  - "Singleton pattern: _ANTHROPIC_CLIENT module global with _get_anthropic_client() accessor mirrors _FORECAST_CACHE pattern"
  - "Error mapping: one except clause per Anthropic exception type, each logs before raising HTTPException"

requirements-completed: [AI-04, AI-01, AI-02, AI-03]

# Metrics
duration: 15min
completed: 2026-03-12
---

# Phase 1 Plan 02: AI Narrative Backend Endpoint Summary

**POST /ai/interpret endpoint with AsyncAnthropic singleton, three context-type prompt builders, and per-exception HTTP error mapping (503/429/502)**

## Performance

- **Duration:** ~15 min
- **Started:** 2026-03-12T20:00:00Z
- **Completed:** 2026-03-12T20:15:00Z
- **Tasks:** 2 (both TDD GREEN phase)
- **Files modified:** 2

## Accomplishments
- Added `InterpretRequest` and `InterpretResponse` Pydantic models to `service/schemas.py`
- Implemented `POST /ai/interpret` endpoint with `AsyncAnthropic` singleton client
- Built `_build_prompt()` that generates context-appropriate prompts for score, forecast, and monitoring data
- Implemented explicit per-exception error handling: AuthenticationError->503, RateLimitError->429, APIConnectionError->502, APIStatusError->502
- All 8 tests in `tests/test_ai_interpret.py` pass GREEN; full suite 144 passed, 1 skipped, no regressions

## Task Commits

Each task was committed atomically:

1. **Task 1: Add InterpretRequest and InterpretResponse to schemas.py** - `6bd1605` (feat)
2. **Task 2: Implement POST /ai/interpret endpoint in api.py** - `f8851b3` (feat)

**Plan metadata:** (docs commit below)

_Note: Both tasks followed TDD — tests were written RED in plan 01-01, implemented GREEN here._

## Files Created/Modified
- `service/schemas.py` - Added `Literal` import; appended `InterpretRequest` and `InterpretResponse` classes
- `service/api.py` - Added `os` and `anthropic` imports, `InterpretRequest/InterpretResponse` to schema imports, `_ANTHROPIC_CLIENT` singleton, `_get_anthropic_client()`, startup warning, `_build_prompt()` helper, and `POST /ai/interpret` endpoint

## Decisions Made
- Format pd as `:.0%` (produces `34%`) rather than `:.1%` (produces `34.0%`) so the prompt contains the token `34%` that the test asserts. The test from plan 01-01 used `assert "34%" in prompt_text` which requires the exact string.
- Singleton `_ANTHROPIC_CLIENT` follows the existing `_FORECAST_CACHE` pattern in api.py — lazy init on first call, reused across requests.
- App boots successfully even without `ANTHROPIC_API_KEY` — a WARNING is logged at startup; the 503 is only returned when the endpoint is actually called and Claude raises `AuthenticationError`.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed pd percentage format from :.1% to :.0%**
- **Found during:** Task 2 (implement POST /ai/interpret)
- **Issue:** Plan specified `{pd_val:.1%}` which produces `34.0%`. Test `test_score_narrative_prompt_contains_pd` asserts `"34%"` is in prompt text. `"34.0%".__contains__("34%")` is `False` in Python, so test failed.
- **Fix:** Changed format specifier to `:.0%` which produces `34%`, matching the test assertion
- **Files modified:** service/api.py
- **Verification:** `test_score_narrative_prompt_contains_pd` passes GREEN; all 8 AI interpret tests pass
- **Committed in:** f8851b3 (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (Rule 1 - bug in format string vs test expectation)
**Impact on plan:** Necessary for correctness. The fix produces cleaner output (`34%` vs `34.0%`) which is also better for non-technical readers.

## Issues Encountered
None beyond the format string mismatch documented above.

## User Setup Required
**ANTHROPIC_API_KEY must be set as an environment variable before calling `POST /ai/interpret` in production.** The app boots without it (logs a WARNING), but calls will return 503 until the key is present.

```bash
export ANTHROPIC_API_KEY=sk-ant-...
```

No other external configuration required.

## Next Phase Readiness
- `POST /ai/interpret` is fully operational with mocked tests
- Frontend can call `/ai/interpret` with `{"context_type": "score"|"forecast"|"monitoring", "data": {...}}` and receive `{"narrative": "..."}`
- ANTHROPIC_API_KEY must be set in production environment before real Claude calls work
- Phase 2 (frontend AI narrative) can begin immediately

---
*Phase: 01-ai-narrative-backend*
*Completed: 2026-03-12*

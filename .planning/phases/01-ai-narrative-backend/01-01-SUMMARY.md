---
phase: 01-ai-narrative-backend
plan: "01"
subsystem: testing
tags: [anthropic, tdd, pytest, fastapi, ai-narrative]

# Dependency graph
requires: []
provides:
  - "anthropic>=0.84 installed and in pyproject.toml dependencies"
  - "tests/test_ai_interpret.py: 8-test scaffold defining POST /ai/interpret expected behaviors"
  - "Mock AsyncAnthropic fixture pattern using patch with create=True for pre-implementation patching"
affects:
  - 01-02-PLAN (implements the endpoint these tests define)

# Tech tracking
tech-stack:
  added: ["anthropic>=0.84"]
  patterns:
    - "TDD RED scaffold: write tests against non-existent endpoint, use patch(create=True) to mock missing attributes"
    - "monkeypatch.setattr(raising=False) for setting attributes that don't exist yet on api module"

key-files:
  created:
    - "tests/test_ai_interpret.py"
  modified:
    - "pyproject.toml"

key-decisions:
  - "Used patch(..., create=True) in mock_anthropic_client fixture so fixture works before _get_anthropic_client exists in service.api"
  - "Used monkeypatch.setattr(raising=False) in error tests so tests fail at assertion (404) rather than on setup AttributeError"
  - "Prompt content assertions use loose matching (any() of plausible tokens) to avoid brittleness over exact formatting"

patterns-established:
  - "AI mock pattern: patch service.api._get_anthropic_client with create=True, MagicMock().messages.create = AsyncMock returning canned message"
  - "Error simulation: anthropic.AuthenticationError/RateLimitError instantiated with MagicMock() as response kwarg"

requirements-completed: ["AI-05"]

# Metrics
duration: 3min
completed: 2026-03-12
---

# Phase 1 Plan 01: AI Narrative Test Scaffold Summary

**anthropic>=0.84 added to pyproject.toml and 8-test RED scaffold created for POST /ai/interpret covering score/forecast/monitoring narratives, auth error 503, rate limit 429, invalid context 422, and prompt content assertions**

## Performance

- **Duration:** 3 min
- **Started:** 2026-03-12T19:54:39Z
- **Completed:** 2026-03-12T19:57:21Z
- **Tasks:** 1
- **Files modified:** 2

## Accomplishments
- Installed anthropic SDK v0.84.0 and pinned it in pyproject.toml
- Created 8-test scaffold in tests/test_ai_interpret.py covering all AI-01 through AI-05 behaviors
- Established mock AsyncAnthropic fixture pattern using patch(create=True) to enable RED-phase testing before implementation
- All 8 tests collected by pytest; 7 fail RED (404 - endpoint not yet built), 1 passes (importability check)

## Task Commits

Each task was committed atomically:

1. **Task 1: Add anthropic dependency and create test scaffold** - `8689103` (test)

**Plan metadata:** *(docs commit follows)*

_Note: TDD task at RED phase — GREEN commit will occur in Plan 02 after endpoint implementation_

## Files Created/Modified
- `tests/test_ai_interpret.py` - 8-test scaffold for POST /ai/interpret with mock AsyncAnthropic fixture
- `pyproject.toml` - Added `"anthropic>=0.84"` to project dependencies

## Decisions Made
- Used `patch(..., create=True)` so the mock fixture works before `_get_anthropic_client` exists in `service.api` — prevents AttributeError on fixture setup while keeping tests properly RED at assertion level
- Used `monkeypatch.setattr(raising=False)` in error tests for same reason
- Prompt content assertions use `any()` across multiple plausible token formats (e.g., `"20%"`, `"0.20"`, `"0.2"`, `"threshold"`) to avoid brittleness when Plan 02 chooses exact formatting

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed AttributeError in mock fixture and error tests**
- **Found during:** Task 1 (test scaffold creation)
- **Issue:** `patch("service.api._get_anthropic_client")` raises AttributeError when attribute doesn't exist; `monkeypatch.setattr(raising=True)` (default) also raises AttributeError on non-existent attributes
- **Fix:** Added `create=True` to patch call in fixture; added `raising=False` to monkeypatch.setattr calls in error tests
- **Files modified:** tests/test_ai_interpret.py
- **Verification:** pytest collects 8 tests, 7 fail at assertion (404) not at setup
- **Committed in:** 8689103 (Task 1 commit)

---

**Total deviations:** 1 auto-fixed (Rule 1 — bug in test setup)
**Impact on plan:** Essential fix — without it tests error on setup instead of failing RED at assertion. No scope creep.

## Issues Encountered
- `pip install anthropic>=0.84` produced dependency conflict warnings for langchain-related packages (pre-existing environment issue, not related to this project). anthropic installed successfully at 0.84.0 and is importable.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Test scaffold complete and RED; Plan 02 can implement `POST /ai/interpret` endpoint to turn tests GREEN
- `_get_anthropic_client` function must be added to `service/api.py` (tests mock this exact name)
- Endpoint must handle: `context_type` enum validation (422), `anthropic.AuthenticationError` → 503, `anthropic.RateLimitError` → 429
- Prompt content tests expect pd value formatted as percentage, threshold info, and drift/psi keywords in messages sent to Claude

---
*Phase: 01-ai-narrative-backend*
*Completed: 2026-03-12*

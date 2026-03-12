# Phase 1: AI Narrative Backend - Research

**Researched:** 2026-03-12
**Domain:** Anthropic Python SDK, FastAPI endpoint design, AI narrative generation
**Confidence:** HIGH

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| AI-01 | User sees plain-language AI-written interpretation after scoring a single loan | Prompt design patterns for loan score + top_factors → narrative text |
| AI-02 | User sees plain-language AI-written interpretation after running a forecast | Prompt design for forecast rows + threshold exceedance → narrative text |
| AI-03 | User sees plain-language AI-written monitoring status | Prompt design for drift_features + score_drift + perf_drift JSON → narrative text |
| AI-04 | Backend exposes POST /ai/interpret endpoint calling Claude claude-sonnet-4-6 server-side using ANTHROPIC_API_KEY | AsyncAnthropic client in FastAPI, env var pattern, error handling |
| AI-05 | anthropic Python package added to project dependencies | `anthropic>=0.84` added to pyproject.toml dependencies |
</phase_requirements>

---

## Summary

This phase adds a single new FastAPI endpoint — `POST /ai/interpret` — that accepts model output JSON (score, forecast, or monitoring data), calls the Anthropic Claude claude-sonnet-4-6 API server-side, and returns a plain-language narrative string. The frontend then renders that string below the relevant panel output. No API key is ever sent to the browser.

The Anthropic Python SDK (`anthropic>=0.84`) provides `AsyncAnthropic` which integrates cleanly with FastAPI's async request handlers. The pattern is: receive a typed Pydantic request body describing the `context_type` (score/forecast/monitoring) and the raw model output data, construct a prompt, call `client.messages.create(model="claude-sonnet-4-6", ...)`, and return `message.content[0].text`. Error handling must explicitly trap `AuthenticationError`, `RateLimitError`, and `APIStatusError` — the existing `api.py` broad exception handlers must NOT be used for Claude API calls.

The frontend side requires small, targeted additions to `app.js`: after each successful score/forecast/monitoring call, POST to `/ai/interpret` and inject the returned narrative string into a `<p>` element below the existing output `<pre>`. No framework, no new build step, no stylesheet rewrite — all consistent with existing vanilla JS patterns.

**Primary recommendation:** Use `AsyncAnthropic` client instantiated once at module level in `api.py`, add `InterpretRequest` / `InterpretResponse` Pydantic schemas to `schemas.py`, and write the `POST /ai/interpret` handler following the same pattern as the existing `async def forecast(...)` handler.

---

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| anthropic | >=0.84.0 | Anthropic Claude API client | Official SDK, auto-reads ANTHROPIC_API_KEY, provides AsyncAnthropic for FastAPI |
| fastapi | 0.111.1 (existing) | HTTP framework | Already in use — new endpoint follows existing patterns |
| pydantic | 2.7.4 (existing) | Request/response validation | Already in use — new schemas in schemas.py |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| os (stdlib) | — | Read env var ANTHROPIC_API_KEY | Fallback if SDK doesn't read env automatically (SDK reads it by default) |
| httpx | 0.27.0 (existing) | Underlying HTTP transport for anthropic SDK | Already in pyproject.toml — no additional install needed |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| AsyncAnthropic | Sync Anthropic | Sync blocks FastAPI event loop — use async in all async route handlers |
| Direct messages.create | Streaming | Streaming adds frontend complexity (EventSource); narrative is short, non-streaming is sufficient |
| anthropic SDK | Direct httpx calls | SDK handles auth, retries, typed errors — no reason to hand-roll |

**Installation:**
```bash
pip install "anthropic>=0.84"
```
Add to `pyproject.toml` under `[project] dependencies`:
```
"anthropic>=0.84",
```

---

## Architecture Patterns

### Recommended Project Structure

No new files or directories are required. All additions are targeted:

```
service/
├── api.py          # Add POST /ai/interpret endpoint + AsyncAnthropic client init
├── schemas.py      # Add InterpretRequest, InterpretResponse Pydantic models
└── static/
    └── app.js      # Add fetchNarrative() helper, call after score/forecast/monitoring
```

### Pattern 1: AsyncAnthropic Client — Module-Level Singleton

**What:** Instantiate `AsyncAnthropic` once at module level in `api.py`, similar to `scoring_model` and `_FORECAST_CACHE`. The SDK reads `ANTHROPIC_API_KEY` automatically from the environment.

**When to use:** All async FastAPI endpoints — avoids creating a new HTTP connection pool on every request.

**Example:**
```python
# Source: https://github.com/anthropics/anthropic-sdk-python README
import anthropic

_ANTHROPIC_CLIENT: anthropic.AsyncAnthropic | None = None

def _get_anthropic_client() -> anthropic.AsyncAnthropic:
    global _ANTHROPIC_CLIENT
    if _ANTHROPIC_CLIENT is None:
        _ANTHROPIC_CLIENT = anthropic.AsyncAnthropic()
        # SDK auto-reads ANTHROPIC_API_KEY from environment
    return _ANTHROPIC_CLIENT
```

### Pattern 2: POST /ai/interpret Endpoint

**What:** Accepts a typed payload with `context_type` (enum: "score" | "forecast" | "monitoring") and a `data` dict containing the raw model output. Dispatches to a prompt-builder function, calls Claude, returns narrative text.

**When to use:** Single endpoint for all three narrative types — simpler frontend contract than three separate endpoints.

**Example:**
```python
# Source: https://platform.claude.com/docs/en/api/messages + existing api.py patterns
@app.post("/ai/interpret", response_model=InterpretResponse, tags=["ai"])
async def ai_interpret(req: InterpretRequest) -> InterpretResponse:
    client = _get_anthropic_client()
    prompt = _build_prompt(req.context_type, req.data)
    try:
        message = await client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=300,
            system="You are a concise risk analyst. Write 2-3 sentences in plain English.",
            messages=[{"role": "user", "content": prompt}],
        )
        narrative = message.content[0].text
    except anthropic.AuthenticationError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                            detail="AI narrative unavailable: invalid API key") from exc
    except anthropic.RateLimitError as exc:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                            detail="AI narrative unavailable: rate limited") from exc
    except anthropic.APIStatusError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY,
                            detail=f"AI narrative unavailable: {exc.status_code}") from exc
    return InterpretResponse(narrative=narrative)
```

### Pattern 3: Pydantic Schemas

**What:** Two new schemas in `schemas.py` — `InterpretRequest` and `InterpretResponse`.

```python
# Add to service/schemas.py
from typing import Literal

class InterpretRequest(BaseModel):
    context_type: Literal["score", "forecast", "monitoring"]
    data: dict[str, Any] = Field(description="Raw model output to interpret")

class InterpretResponse(BaseModel):
    narrative: str = Field(description="Plain-language AI interpretation")
```

### Pattern 4: Prompt Construction

**What:** Three distinct prompt-builder branches keyed on `context_type`. Each extracts the relevant fields from `data` and formats a concise prompt. Prompts must include numeric values explicitly — Claude cannot infer them.

**Score prompt example:**
```python
def _build_prompt(context_type: str, data: dict) -> str:
    if context_type == "score":
        pd = data.get("pd", "unknown")
        decision = data.get("decision", "unknown")
        factors = data.get("top_factors", [])
        factor_str = ", ".join(f["name"] for f in factors[:3]) if factors else "none identified"
        return (
            f"A mortgage loan was scored. Default probability: {pd:.1%}. "
            f"Decision: {decision}. Top risk factors: {factor_str}. "
            "Write a 2-sentence plain-language interpretation for a non-technical reader."
        )
    elif context_type == "forecast":
        ...
    elif context_type == "monitoring":
        ...
```

### Pattern 5: Frontend Narrative Injection (Vanilla JS)

**What:** After a successful score/forecast call, POST to `/ai/interpret` and insert the narrative into a pre-existing or newly added `<p id="scoreNarrative">` element.

```javascript
// app.js addition — follows existing fetch/readJson pattern
async function fetchNarrative(contextType, data) {
  try {
    const result = await fetch("/ai/interpret", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ context_type: contextType, data }),
    }).then(readJson);
    return result.narrative;
  } catch {
    return null; // narrative is non-critical — degrade silently
  }
}
```

### Anti-Patterns to Avoid

- **Sync Anthropic client in async handlers:** `Anthropic()` (sync) in an `async def` route blocks the event loop. Always use `AsyncAnthropic`.
- **Re-raising raw Claude errors as 500s:** Map specific error types to appropriate HTTP codes (503 for auth, 429 for rate limit, 502 for upstream errors). Never use the existing broad `except Exception` handler for Claude calls.
- **Exposing ANTHROPIC_API_KEY in responses:** The key must never appear in any response body, log line, or error message. The SDK reads it internally — never echo it back.
- **Calling `/ai/interpret` before the primary response:** Always resolve the score/forecast/monitoring call first, then call interpret as a secondary enrichment step. A Claude API failure must not break the primary score result.
- **Large max_tokens for short narratives:** Narratives are 2-3 sentences. `max_tokens=300` is sufficient. Larger limits waste quota and slow response.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| HTTP client for Anthropic API | Custom httpx calls with auth headers | `anthropic.AsyncAnthropic` | SDK handles auth signing, retries, typed error hierarchy, response parsing |
| Retry logic for rate limits | Custom sleep/retry loop | SDK's built-in retry (`max_retries` param) | SDK implements exponential backoff on 429s automatically |
| API key validation | Pre-flight key check | Catch `AuthenticationError` at request time | Avoids extra API round-trip; handles key rotation naturally |
| Response text extraction | Parsing raw response dict | `message.content[0].text` | SDK returns typed `Message` object with `.content` list of `TextBlock` |

**Key insight:** The anthropic SDK handles all transport complexity. The only application code needed is prompt construction and error mapping.

---

## Common Pitfalls

### Pitfall 1: Blocking the FastAPI Event Loop
**What goes wrong:** Using `Anthropic()` (sync) client in an `async def` route handler blocks the event loop for the duration of the Claude API call (typically 1-3 seconds), degrading all concurrent requests.
**Why it happens:** Sync HTTP calls use `httpx` in blocking mode — incompatible with asyncio.
**How to avoid:** Import and instantiate `AsyncAnthropic` exclusively. The async version uses `httpx.AsyncClient` internally.
**Warning signs:** Unusually slow concurrent requests; no obvious error in logs.

### Pitfall 2: Missing ANTHROPIC_API_KEY at Startup
**What goes wrong:** `POST /ai/interpret` returns 503 with unhelpful error on first call. The model is running but AI narrative is broken.
**Why it happens:** ANTHROPIC_API_KEY is not set in the deployment environment.
**How to avoid:** Add a startup warning log in `lifespan()` if the env var is absent. Do not raise at startup (app should boot without it — graceful degradation). Catch `AuthenticationError` and return a clear 503.
**Warning signs:** `anthropic.AuthenticationError` in logs.

### Pitfall 3: Claude Errors Silently Masked by Broad Exception Handlers
**What goes wrong:** `STATE.md` explicitly flags that `service/api.py` has broad `except Exception` handlers that silently swallow errors. If the new endpoint inherits this pattern, Claude API failures disappear from logs.
**Why it happens:** Copy-paste from existing endpoint patterns.
**How to avoid:** Write explicit `except anthropic.AuthenticationError`, `except anthropic.RateLimitError`, `except anthropic.APIStatusError` blocks. Log each with `log.error()` before raising the HTTPException.
**Warning signs:** Users see no narrative but no error in logs either.

### Pitfall 4: Frontend Narrative Failure Breaks Primary Flow
**What goes wrong:** If `/ai/interpret` fails (Claude down, rate limited), the score or forecast result is also lost because the narrative fetch throws and overwrites the output area.
**Why it happens:** Narrative fetch error handling not isolated from primary result display.
**How to avoid:** Call `fetchNarrative()` in a `try/catch` that degrades gracefully — show "Narrative unavailable" or nothing, but always display the primary numeric result first.
**Warning signs:** Users report "score disappeared" during Claude outages.

### Pitfall 5: Prompt Producing Unhelpful Output
**What goes wrong:** Claude returns vague or hallucinated narrative because the prompt lacks concrete numeric values.
**Why it happens:** Prompt passes only field names without values (e.g., "interpret the score" with no actual numbers).
**How to avoid:** Always embed the key numeric values directly in the prompt string: `f"Default probability: {pd:.1%}. Decision: {decision}."` Test prompts manually before writing unit tests.
**Warning signs:** Narrative text contains phrases like "the score suggests" without any numbers.

---

## Code Examples

Verified patterns from official sources:

### AsyncAnthropic Basic Call
```python
# Source: https://github.com/anthropics/anthropic-sdk-python README (v0.84.0)
import anthropic

client = anthropic.AsyncAnthropic()
# ANTHROPIC_API_KEY read automatically from environment

message = await client.messages.create(
    model="claude-sonnet-4-6",
    max_tokens=300,
    messages=[{"role": "user", "content": "Hello"}],
)
text = message.content[0].text
```

### Error Handling (All Three Required Types)
```python
# Source: https://docs.anthropic.com/en/api/errors (redirects to platform.claude.com)
import anthropic

try:
    message = await client.messages.create(...)
except anthropic.APIConnectionError as exc:
    # Network-level failure (DNS, timeout, connection refused)
    log.error("Claude API connection error: {}", exc)
    raise HTTPException(status_code=502, detail="AI service unreachable") from exc
except anthropic.AuthenticationError as exc:
    # HTTP 401 — invalid or missing API key
    log.error("Claude authentication error: {}", exc)
    raise HTTPException(status_code=503, detail="AI service authentication failed") from exc
except anthropic.RateLimitError as exc:
    # HTTP 429 — quota or rate limit exceeded
    log.warning("Claude rate limit hit: {}", exc)
    raise HTTPException(status_code=429, detail="AI service rate limited") from exc
except anthropic.APIStatusError as exc:
    # Any other 4xx/5xx from Anthropic
    log.error("Claude API error {}: {}", exc.status_code, exc.message)
    raise HTTPException(status_code=502, detail=f"AI service error: {exc.status_code}") from exc
```

### Extracting Narrative Text
```python
# Source: SDK response model — content is list[TextBlock | ToolUseBlock | ThinkingBlock]
# For narrative-only calls (no tools, no thinking), content[0] is always TextBlock
message = await client.messages.create(
    model="claude-sonnet-4-6",
    max_tokens=300,
    messages=[{"role": "user", "content": prompt}],
)
# Safe extraction:
if message.content and hasattr(message.content[0], "text"):
    narrative = message.content[0].text
else:
    narrative = "Interpretation unavailable."
```

### pyproject.toml Dependency Addition
```toml
# Add to [project] dependencies list in pyproject.toml
"anthropic>=0.84",
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `anthropic.Anthropic` in async code | `anthropic.AsyncAnthropic` | SDK >= 0.3 | Required for FastAPI; sync blocks event loop |
| Pinned exact version (e.g. `anthropic==0.84.0`) | Minimum version constraint (`anthropic>=0.84`) | Best practice | Allows patch updates without re-pinning |
| Checking `message.content[0]["text"]` (dict access) | `message.content[0].text` (attribute access) | SDK >= 0.5 | SDK returns typed objects, not raw dicts |

**Deprecated/outdated:**
- `anthropic.Anthropic` (sync client): Still valid for non-async scripts, but must NOT be used in FastAPI async handlers.
- Direct REST calls to `api.anthropic.com`: Always use the SDK — it handles auth header signing, retry logic, and response parsing.

---

## Open Questions

1. **`top_factors` can be an empty list**
   - What we know: `STATE.md` explicitly flags that `top_factors` returns empty list silently if SHAP extraction fails.
   - What's unclear: Whether factor-less score prompts produce useful narratives or degrade to vague output.
   - Recommendation: Prompt builder must handle empty `top_factors` gracefully: omit factor text entirely rather than saying "top factors: none". Test with empty factors list.

2. **Monitoring data may be unavailable (`available: false`)**
   - What we know: `GET /monitoring/summary` returns `available: false` when no monitoring jobs have run.
   - What's unclear: Should `/ai/interpret` with monitoring context be callable when monitoring data is absent?
   - Recommendation: Frontend should only call `/ai/interpret` for monitoring when `available: true`. Backend should validate that `data` contains meaningful fields before calling Claude — return a 422 with clear message if data is empty.

3. **ANTHROPIC_API_KEY environment setup for local development**
   - What we know: Key must be set before the endpoint is testable.
   - What's unclear: Whether a `.env` file loader (e.g. python-dotenv) is already used in this project.
   - Recommendation: Check if `pydantic-settings` (already in deps) supports `.env` loading in `config/settings.py`. If so, document that `ANTHROPIC_API_KEY` can be added to a local `.env` file. Do not add `python-dotenv` as a separate dependency.

---

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 8.2.2 |
| Config file | `pyproject.toml` `[tool.pytest.ini_options]` |
| Quick run command | `pytest tests/test_ai_interpret.py -x -v` |
| Full suite command | `pytest tests/ -v` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| AI-04 | POST /ai/interpret with mock client returns 200 + narrative string | unit | `pytest tests/test_ai_interpret.py::test_interpret_score_returns_narrative -x` | Wave 0 |
| AI-04 | POST /ai/interpret with missing API key returns 503 | unit | `pytest tests/test_ai_interpret.py::test_interpret_auth_error_returns_503 -x` | Wave 0 |
| AI-04 | POST /ai/interpret with rate limit returns 429 | unit | `pytest tests/test_ai_interpret.py::test_interpret_rate_limit_returns_429 -x` | Wave 0 |
| AI-04 | POST /ai/interpret with invalid context_type returns 422 | unit | `pytest tests/test_ai_interpret.py::test_interpret_invalid_context_type_returns_422 -x` | Wave 0 |
| AI-01 | Score endpoint response + narrative — integration smoke | smoke | `pytest tests/test_ai_interpret.py::test_score_narrative_prompt_contains_pd -x` | Wave 0 |
| AI-02 | Forecast narrative prompt contains threshold and period info | unit | `pytest tests/test_ai_interpret.py::test_forecast_narrative_prompt_contains_threshold -x` | Wave 0 |
| AI-03 | Monitoring narrative prompt reflects drift severity | unit | `pytest tests/test_ai_interpret.py::test_monitoring_narrative_prompt_reflects_drift -x` | Wave 0 |
| AI-05 | anthropic package importable | smoke | `pytest tests/test_ai_interpret.py::test_anthropic_importable -x` | Wave 0 |

**Note:** All tests mock `AsyncAnthropic.messages.create` — no real API calls in test suite. Use `unittest.mock.AsyncMock` or `pytest-mock`.

### Sampling Rate
- **Per task commit:** `pytest tests/test_ai_interpret.py -x -v`
- **Per wave merge:** `pytest tests/ -v`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_ai_interpret.py` — covers AI-01 through AI-05 (does not exist yet)
- [ ] Shared fixture: mock `AsyncAnthropic` client returning stub narrative — add to `tests/test_ai_interpret.py` as a local fixture (no conftest changes needed)
- [ ] `anthropic>=0.84` installable: `pip install "anthropic>=0.84"` — verify in CI environment

---

## Sources

### Primary (HIGH confidence)
- `https://github.com/anthropics/anthropic-sdk-python` — SDK README, version 0.84.0 (Feb 25, 2026), AsyncAnthropic usage pattern, env var behavior
- `https://pypi.org/project/anthropic/` — Version 0.84.0 confirmed as latest as of 2026-03-12
- `https://platform.claude.com/docs/en/api/messages` — Messages API parameters, response format, error types, async FastAPI pattern
- Existing codebase: `service/api.py`, `service/schemas.py`, `service/static/app.js`, `tests/test_api_contract.py` — patterns verified by direct read

### Secondary (MEDIUM confidence)
- `https://docs.anthropic.com/en/api/errors` (redirects to platform.claude.com) — Error type hierarchy verified against SDK README

### Tertiary (LOW confidence)
- None — all critical claims verified via official sources or direct codebase inspection.

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — anthropic 0.84.0 confirmed on PyPI; FastAPI + pydantic already in codebase
- Architecture: HIGH — endpoint pattern confirmed against existing `api.py`; SDK async pattern confirmed from official README
- Pitfalls: HIGH — pitfalls 1-4 derived from direct codebase inspection (STATE.md blockers, api.py broad exception handlers); pitfall 5 from API pattern knowledge
- Validation architecture: HIGH — pytest already configured in pyproject.toml; test patterns match existing test files

**Research date:** 2026-03-12
**Valid until:** 2026-04-12 (anthropic SDK moves fast; re-verify version if > 30 days old)

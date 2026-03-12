# Coding Conventions

**Analysis Date:** 2026-03-12

## Naming Patterns

**Files:**
- Snake_case for all Python files: `settings.py`, `ingest_fred.py`, `build_features.py`
- Test files use `test_*.py` pattern: `test_features.py`, `test_settings.py`
- Module directories use snake_case: `data_ingestion/`, `feature_defs/`, `training/`
- Private modules (implementation details) prefix with underscore: `_log_upb()`, `_fetch_series_api()`

**Functions:**
- Camel case for public functions: `build_features()`, `configure_logging()`, `ingest_fred()`
- Lowercase with underscores for private functions: `_fetch_series_api()`, `_load_config()`, `_clip()`
- Predicates use `is_*` prefix: `_is_fthb()`, `_is_high_ltv()`, `_is_high_dti()`, `_is_arm()`
- CLI commands use single-word lowercase: `ingest`, `features`, `train`, `serve`, `pipeline`, `monitor`

**Variables:**
- Lowercase with underscores: `series_id`, `api_key`, `numeric_orig_cols`, `performance_df`
- Constants use SCREAMING_SNAKE_CASE: `_LOG_UPB_CLIP`, `_PD_FEATURE_COLS`, `_LABEL_COL`, `_FORECAST_CACHE`
- Private module-level constants prefix with underscore: `_DATA_PATHS`, `_CONFIG_PATH`, `_STATIC_DIR`, `_MODEL_NAMES`
- Temporary/loop variables keep simple names: `df`, `col`, `s` (for Series), `fh` (file handle)

**Types:**
- Type aliases use CamelCase: `FeatureFn = Callable[[pd.DataFrame], pd.Series | pd.DataFrame]`
- Dataclasses use CamelCase: `FeatureSpec`, `SplitResult`, `Settings`
- Type hints use `|` for unions (PEP 604, Python 3.10+ style): `str | None`, `pd.Series | pd.DataFrame`
- Type hints on all function signatures (enforced by mypy strict mode)

## Code Style

**Formatting:**
- Tool: Ruff formatter (via `ruff format` command)
- Line length: 100 characters (configured in `pyproject.toml`)
- Indentation: 4 spaces (Ruff default)

**Linting:**
- Tool: Ruff with selective rules
- Enabled rules in `pyproject.toml`: E (pycodestyle), W (warnings), F (Pyflakes), I (isort), UP (pyupgrade), B (bugbear), SIM (simplify)
- Ignored rule: E501 (line too long — formatting is handled by formatter)
- Run via `make lint` or `ruff check .`

**File structure:**
- Future imports at top: `from __future__ import annotations`
- Module docstring immediately after future imports explaining purpose and usage
- Section dividers: `# ─────────────────────────────` for major sections within files
- Blank lines: Two lines between module-level definitions, one line within classes

## Import Organization

**Order (enforced by Ruff isort):**
1. `from __future__ import annotations` (always first)
2. Standard library imports (`io`, `sys`, `pathlib`, etc.)
3. Third-party imports (`pandas`, `numpy`, `fastapi`, `pydantic`, etc.)
4. Local imports from known first-party packages (configured in `pyproject.toml`):
   - `data_ingestion`, `features`, `training`, `models`, `service`, `monitoring`, `config`, `utils`

**Path Aliases:**
No path aliases configured; all local imports use full relative imports from project root:
- `from data_ingestion.loader import load`
- `from features.engineer import build_features`
- `from config.settings import settings`
- `from utils.logging import log`

**Relative vs Absolute:**
- Always use absolute imports from project root (no relative imports like `from . import X`)
- Facilitates CLI invocation via `python -m main`

## Error Handling

**Patterns:**
- Use specific exception types, not bare `except Exception`
- Raise `ValueError` for invalid input: `raise ValueError("Unknown source key")`
- Raise `FileNotFoundError` for missing files: `raise FileNotFoundError(f"CSV file not found: {p}")`
- Raise `RuntimeError` for operation failures: `raise RuntimeError("FRED API request failed")`
- Use `errors="coerce"` in pandas numeric conversions: `pd.to_numeric(df[col], errors="coerce")`

**Logging on error:**
- Log context before raising: `log.error("Failed to load {}: {}", path, exc)`
- Catch specific exceptions and log, then re-raise or handle gracefully
- Use `log.warning()` for recoverable issues (skipped features, fallbacks)
- Use `log.debug()` for detailed diagnostic info (fetch operations, config loading)

## Logging

**Framework:** Loguru (`from utils.logging import log`)

**Module setup:**
- Import configured logger: `from utils.logging import log`
- Never create per-module loggers; use the global singleton

**Patterns:**
- Info level for progress milestones: `log.info("Starting ingestion for source={}", source)`
- Debug level for detailed operations: `log.debug("FRED API → {}", series_id)`
- Warning level for recoverable issues: `log.warning("Feature '{}' skipped — missing column {}", spec.name, exc)`
- Use named placeholders for formatting: `log.info("Training complete: {} rows", len(df))`
- Loguru interpolates at log time, use `{}` not f-strings

**Configuration:**
- Configured in `utils/logging.py` via `configure_logging()` function
- Color-coded console output by level
- File rotation at 10 MB with 14-day retention
- JSON serialization available (set `log_serialize=True` in settings)
- Configured at app startup via main.py or FastAPI lifespan

## Comments

**When to Comment:**
- Use comments for non-obvious algorithmic intent, not code repetition
- Explain WHY decisions were made, not WHAT the code does
- Use section dividers (`# ─────`) to organize large functions
- Document business logic constraints (e.g., "Leakage guard: sort performance by (loan, period) before any feature")

**Docstring Style:** Google-style docstrings with Args/Returns/Usage sections

```python
def build_features(
    origination_df: pd.DataFrame,
    performance_df: pd.DataFrame | None = None,
    groups: list[str] | None = None,
) -> pd.DataFrame:
    """Build features from origination (and optionally performance) DataFrames.

    Args:
        origination_df:  Validated origination parquet contents.
        performance_df:  Monthly performance data (required for performance group).
        groups:          Feature groups to run; ``None`` reads from features.yaml.

    Returns:
        Feature DataFrame indexed by ``loan_sequence_number``.
    """
```

**Module-level docstrings:**
- Explain module purpose in 1-2 lines
- Include Authentication section if needed (e.g., FRED API key requirement)
- Include Usage section with CLI and programmatic examples
- Use reStructuredText backticks for code: `` `variable_name` ``

## Function Design

**Size:** Keep functions under ~50 lines; break complex logic into private helpers

**Parameters:**
- Use explicit parameters (no `*args/**kwargs` unless necessary)
- Use type hints on all parameters
- Use default values thoughtfully (None, not mutable defaults)
- Document parameter constraints in docstring (e.g., `ge=0.05, le=0.5` in Pydantic Field)

**Return Values:**
- Always specify return type in signature
- Return None explicitly for no-return functions
- Return multiple values as tuple or dataclass, never bare tuples:
  ```python
  @dataclass
  class SplitResult:
      train: pd.DataFrame
      val: pd.DataFrame
      test: pd.DataFrame
  ```

**Validation:**
- Use Pydantic for configuration validation: `Settings` inherits from `BaseSettings` with Field constraints
- Use Pandera for DataFrame schema validation at ingestion boundaries
- Coerce data types in pandas operations (never trust upstream column types)

## Module Design

**Exports:**
- Public functions/classes at module level with clear names
- Private functions/constants prefix with underscore: `_load_config()`, `_CONFIG_PATH`
- Use `__all__` in init files to control public API (not currently used; all non-underscore names are public)

**Barrel Files:**
- Minimal barrel exports in `__init__.py` files
- Example: `features/__init__.py` exports nothing; use full imports like `from features.engineer import build_features`
- Keeps import graph clear and traceable

**Configuration:**
- All config lives in `config/settings.py` via Pydantic Settings
- YAML files for non-secret configs: `config/fred.yaml`, `config/features.yaml`, `config/data_paths.yaml`
- Environment variables via `.env` file (never hardcoded)
- Singleton pattern: `from config.settings import settings` used throughout

## Package Management

**Dependency pinning:**
- All dependencies pinned to exact versions in `pyproject.toml`
- No floating version ranges (e.g., `pandas==2.2.3` not `pandas>=2.0`)
- Enables reproducible builds and predictable behavior

---

*Convention analysis: 2026-03-12*

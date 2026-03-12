# Testing Patterns

**Analysis Date:** 2026-03-12

## Test Framework

**Runner:**
- Pytest 8.2.2
- Config: `pyproject.toml` in `[tool.pytest.ini_options]` section
- Test discovery: `testpaths = ["tests"]` — all tests in `tests/` directory
- Run via `make test` or `pytest`

**Assertion Library:**
- Built-in `assert` statements (Python standard)
- Pytest's `raises()` context manager for exception testing

**Run Commands:**
```bash
make test              # Run all tests with verbose output (-v flag)
make test-cov          # Run tests with coverage report (HTML in htmlcov/)
pytest                 # Run with default settings
pytest -v              # Verbose mode showing each test
pytest tests/test_features.py::test_build_features_delegates_to_pipeline  # Single test
```

**Output:**
- Configured with `log_cli = true` and `log_cli_level = "INFO"` — logs print during test runs
- `-v` flag enabled by default in `addopts` — shows individual test names and outcomes

## Test File Organization

**Location:**
- All tests in `tests/` directory at project root (parallel to source modules)
- Organized by subject module: `tests/test_features.py` tests `features/`, `tests/test_training.py` tests `training/`, etc.
- Test file count: 27 test modules covering data ingestion, feature engineering, training, API contracts, monitoring, auth, and utilities

**Naming:**
- Test modules: `test_*.py` pattern (e.g., `test_features.py`, `test_settings.py`)
- Test functions: `test_*` pattern describing what they test (e.g., `test_build_features_delegates_to_pipeline()`)
- Test fixtures: Defined inline with `@pytest.fixture` decorator or passed as function parameters

**Structure:**
```
tests/
├── test_api_contract.py          # FastAPI endpoint contracts
├── test_auth_user_mode.py        # Authentication and user scoping
├── test_build_features_perf_summary.py  # Feature pipeline details
├── test_calibration.py           # Model calibration
├── test_data_ingestion.py        # Data loader
├── test_demo_forecaster.py       # Demo forecast model
├── test_feature_defs.py          # Feature registry
├── test_features.py              # Feature engineer module
├── test_ingest_fannie.py         # Fannie Mae ingest
├── test_ingest_fred.py           # FRED API ingest
├── test_interpretability.py      # SHAP interpretability
├── test_jobs_api.py              # Job management API
├── test_labels.py                # Label engineering
├── test_logging.py               # Logging configuration
├── test_macro_join.py            # Macro feature joins
├── test_model_lifecycle_api.py   # Model registry API
├── test_model_loader.py          # Model loading
├── test_model_registry.py        # MLflow registry
├── test_monitoring.py            # Monitoring job
├── test_mlflow_training.py       # MLflow integration
├── test_seed_demo.py             # Demo data seeding
├── test_service_smoke.py         # API smoke tests
├── test_settings.py              # Configuration loading
├── test_split.py                 # Train/val/test split
├── test_train_baseline.py        # Baseline training
├── test_train_xgb.py             # XGBoost training
├── test_training.py              # Trainer orchestration
```

## Test Structure

**Suite Organization:**
```python
"""Tests for features."""
from __future__ import annotations

import pandas as pd


def test_build_features_delegates_to_pipeline(monkeypatch) -> None:
    """features.engineer.build_features delegates to build_features.run()."""
    from features import engineer

    expected = pd.DataFrame({"x": [1, 2, 3]})

    def fake_run(source: str, groups=None) -> pd.DataFrame:
        assert source == "fannie-mae"
        assert groups is None
        return expected

    monkeypatch.setattr(engineer, "run_feature_pipeline", fake_run)
    out = engineer.build_features("fannie-mae")
    assert out.equals(expected)
```

**Patterns:**
- Each test file starts with docstring: `"""Tests for [module]."""`
- Future imports: `from __future__ import annotations`
- Standard library/third-party imports at top (pandas, pytest)
- Local imports inside test functions (lazy, for clarity)
- One assertion per test (or related assertions within single logical test)
- Test names describe the behavior being tested, not the mechanism

**Setup/Teardown:**
- No class-based test organization; all tests are functions
- Fixtures passed as function arguments: `def test_auth_register_login_me(client: TestClient) -> None:`
- Monkeypatch fixture for mocking: `monkeypatch.setattr(module, "attribute", mock_value)`
- tmp_path fixture for temporary directories: `def test_from_csv(tmp_path) -> None:`
- Inline fixture definitions with @pytest.fixture decorator

**Example fixture definition:**
```python
@pytest.fixture()
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setattr(auth, "_DB_PATH", tmp_path / "users.sqlite3")
    monkeypatch.setattr(api, "job_manager", JobManager(max_workers=1))
    return TestClient(api.app, raise_server_exceptions=False)
```

## Mocking

**Framework:** Pytest's `monkeypatch` fixture (built-in, no additional mocking library)

**Patterns:**

Basic attribute mocking:
```python
def test_ready_returns_not_ready_when_model_unloaded(monkeypatch) -> None:
    """GET /ready returns 503 until scoring model is loaded."""
    monkeypatch.setattr(type(api.scoring_model), "is_loaded", property(lambda self: False))
    client = TestClient(api.app, raise_server_exceptions=False)
    resp = client.get("/ready")
    assert resp.status_code == 503
```

Function/method mocking:
```python
def test_me_jobs_are_user_scoped(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    import training.trainer as trainer

    monkeypatch.setattr(
        trainer,
        "train_model",
        lambda *args, **kwargs: Path("models/artifacts/users/alice/sklearn-rf.joblib"),
    )
    # ... test continues
```

Dictionary/module attribute mocking:
```python
def test_monitoring_summary_loads_reports(tmp_path: Path, monkeypatch) -> None:
    mon = tmp_path / "monitoring"
    mon.mkdir(parents=True)
    (mon / "summary.md").write_text("# Monitoring Summary")
    monkeypatch.setattr(api, "_MONITORING_DIR", mon)
    # ... test continues
```

**What to Mock:**
- External I/O: filesystem operations, API calls, database connections
- Configuration: environment variables, settings (via monkeypatch)
- Heavy operations: ML model training, long-running processes
- Dependencies: other modules' public functions when testing a specific module in isolation

**What NOT to Mock:**
- Internal helper functions (test the full stack)
- Pandas operations (trust the library)
- Pydantic models (trust the validation)
- Standard library functions (too low-level)
- The code under test (mock dependencies, not the code itself)

## Fixtures and Factories

**Test Data:**

Simple temporary file creation:
```python
def test_from_csv(tmp_path) -> None:
    """from_csv should return a non-empty DataFrame."""
    import pandas as pd
    from data_ingestion.sources import from_csv

    csv_file = tmp_path / "sample.csv"
    csv_file.write_text("date,value\n2024-01-01,100\n2024-01-02,110\n")

    df = from_csv(csv_file)

    assert isinstance(df, pd.DataFrame)
    assert len(df) == 2
    assert list(df.columns) == ["date", "value"]
```

Fixture with dependencies:
```python
@pytest.fixture()
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setattr(auth, "_DB_PATH", tmp_path / "users.sqlite3")
    monkeypatch.setattr(api, "job_manager", JobManager(max_workers=1))
    return TestClient(api.app, raise_server_exceptions=False)
```

Helper function (not a fixture):
```python
def _register_and_login(client: TestClient, username: str, password: str) -> str:
    r = client.post("/auth/register", json={"username": username, "password": password})
    assert r.status_code == 201
    l = client.post("/auth/login", json={"username": username, "password": password})
    assert l.status_code == 200
    return l.json()["access_token"]
```

**Location:**
- Fixtures inline in test files (no conftest.py used currently)
- Shared fixtures should be elevated to a conftest.py if repeated across multiple test files
- Test data (CSV, Parquet) would live in `tests/fixtures/` directory (not yet used in codebase)

## Coverage

**Requirements:** Not enforced (no minimum coverage threshold in `pyproject.toml`)

**View Coverage:**
```bash
make test-cov              # Generate HTML coverage report
# Open htmlcov/index.html in browser
```

**Coverage config in pyproject.toml:**
```toml
[tool.coverage.run]
omit = ["tests/*"]         # Don't measure test code itself
```

**Current gaps:** No explicit coverage metrics enforced; coverage reports are optional diagnostic tools

## Test Types

**Unit Tests (majority of suite):**
- Scope: Individual functions and modules in isolation
- Approach: Mock external dependencies, test logic paths
- Examples: `test_settings_defaults()`, `test_load_unknown_source_raises_value_error()`, `test_build_features_delegates_to_pipeline()`
- Location: `tests/test_*.py` files

**Integration Tests (mixed in unit tests):**
- Scope: Multiple modules working together (no external services)
- Approach: Real DataFrames, real Pydantic validation, real file I/O (using tmp_path)
- Examples: `test_from_csv()` (CSV loading + DataFrame validation), `test_origination_schema_validates_valid_row()` (Pandera schema validation)
- Location: Same test files as unit tests

**Contract Tests (API validation):**
- Scope: FastAPI endpoint contracts and response schemas
- Approach: TestClient with real app instance, no mocking
- Examples: `test_metadata_contract()`, `test_ui_root_serves_html()`, `test_monitoring_summary_loads_reports()`
- Location: `tests/test_api_contract.py`, `tests/test_jobs_api.py`, `tests/test_model_lifecycle_api.py`, `tests/test_auth_user_mode.py`

**E2E Tests:** Not used (would require external services or live endpoints)

## Common Patterns

**Async Testing:**
Not applicable — no async test code in suite. FastAPI tests use TestClient (synchronous wrapper).

**Error Testing:**
```python
def test_train_model_unknown_raises_value_error() -> None:
    """train_model raises ValueError for an unsupported model key."""
    from training.trainer import train_model

    with pytest.raises(ValueError, match="Unknown model"):
        train_model("not-a-real-model")
```

Multiple error conditions:
```python
def test_filter_quarters_restricts() -> None:
    # ... earlier setup
    with pytest.raises(ValueError, match="at least 3 distinct months"):
        # ... code that should raise

def test_normalize_blanks():
    # ... assertion pattern
    assert all(c in pred.columns for c in PROPHET_FORECAST_COLS)
```

**DataFrame Validation:**
```python
def test_split_df_maintains_temporal_order():
    import pandas as pd
    from training.split import split_data

    df = pd.DataFrame({"date": pd.date_range("2020-01-01", periods=100), "value": range(100)})
    r = split_data(df)

    assert r.train["date"].is_monotonic_increasing
    assert r.train["date"].max() < r.val["date"].min()
    assert r.val["date"].max() < r.test["date"].min()
```

**Property Assertions:**
```python
def test_calibrate_ece_decreases():
    # ... calibration logic
    assert len(r.train) + len(r.val) + len(r.test) == len(df)
    assert abs(len(r.train) / n - 0.60) < 0.05
    assert abs(len(r.val) / n - 0.20) < 0.05
```

## Test Execution Details

**Pytest plugins used:**
- pytest-cov (for coverage reports): `make test-cov`
- pytest built-in fixtures: `tmp_path`, `monkeypatch`

**Test discovery:**
- Automatic via `testpaths = ["tests"]` in pyproject.toml
- Collects all `test_*.py` files and functions matching `test_*` pattern

**Execution order:**
- Tests run in file collection order (deterministic based on filesystem)
- No test interdependencies (each test is isolated)
- Monkeypatch/fixtures scoped to individual tests (auto-cleanup)

**Logging during tests:**
- CLI logs enabled: `log_cli = true` in pyproject.toml
- All loguru output appears in test output for debugging
- Can filter with `pytest -k test_name --log-cli-level=DEBUG` for more detail

---

*Testing analysis: 2026-03-12*

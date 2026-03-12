# Codebase Concerns

**Analysis Date:** 2026-03-12

## Tech Debt

**Broad Exception Handling:**
- Issue: Multiple exception handlers catch `Exception` without specificity, silently swallowing error details and making debugging difficult
- Files: `service/api.py` (lines 459, 551, 566, 587), `service/model_loader.py` (lines 112, 134), `training/trainer.py` (lines 313, 341), `monitoring/perf_drift.py` (line 86), `data_ingestion/ingest_fannie.py` (lines 160, 170), `data_ingestion/ingest_fred.py` (line 232)
- Impact: Silent failures in model loading, scoring, and data ingestion. Production errors become difficult to trace. Example at `service/api.py:459` logs only a warning when model activation fails to reload
- Fix approach: Replace broad `except Exception` with specific exception types. Use context managers for proper cleanup. Add structured error tracking/observability

**Forecast Model Caching Without Lifecycle Management:**
- Issue: `_FORECAST_CACHE` dictionary in `service/api.py` line 52 persists Prophet models in memory indefinitely with no eviction, cleanup, or concurrency control
- Files: `service/api.py` (lines 52, 96-101)
- Impact: Memory leak on long-running service. Stale model artifacts loaded multiple times. No thread safety during concurrent requests
- Fix approach: Implement LRU cache with TTL, add cache invalidation on model updates, use `functools.lru_cache` or similar

**Hardcoded Configuration Values:**
- Issue: Magic numbers scattered throughout code without centralized configuration
- Files: `service/auth.py:30` (PBKDF2 iterations: 200_000), `config/settings.py:56` (low_memory_max_train_rows default: 3000), `training/trainer.py:309-310` (Prophet seasonality/changepoint priors)
- Impact: Difficult to tune for different environments or security requirements. PBKDF2 iterations should increase with time as compute improves
- Fix approach: Move all numeric constants to `config/settings.py` with validation and documentation

**In-Memory Job Storage Without Persistence:**
- Issue: `service/jobs.py` JobManager stores all job state in-memory dictionary with no persistence mechanism
- Files: `service/jobs.py` (lines 37, 84-100)
- Impact: Job state lost on service restart. Long-running training/monitoring jobs have no recovery mechanism. No audit trail of executed jobs
- Fix approach: Add backing store (SQLite or file-based) for job history, implement checkpoint/resume logic for long tasks

**Incomplete Feature Engineering Source Registration:**
- Issue: `data_ingestion/sources.py:18` has TODO comment indicating missing data sources
- Files: `data_ingestion/sources.py` (line 18)
- Impact: API documentation promises "from_fred(), from_url(), from_s3(), etc." but only fred/fannie-mae/csv/parquet implemented. Users expect broader integration
- Fix approach: Implement promised sources or remove TODO and update documentation to match actual capabilities

## Known Bugs

**Low-Memory Forecast Fallback Without Testing:**
- Symptoms: Prophet fails in low-memory environments, falls back to lightweight `DemoTrendForecaster` which may produce incorrect forecasts
- Files: `training/trainer.py` (lines 313-321)
- Trigger: Running with `LOW_MEMORY_MODE=true` when Prophet dependencies not fully installed or when memory exhausted during fit
- Workaround: Ensure Prophet installation or disable forecasting in low-memory deployments
- Risk: Silent degradation of forecast quality without user awareness. `DemoTrendForecaster` implements linear trend which may not capture seasonal patterns

**Synthetic Label Generation in PD Scoring:**
- Symptoms: Training data may use synthetic 5% default rate instead of real labels
- Files: `training/trainer.py` (lines 390-394)
- Trigger: Features parquet missing `max_dpd` and `zero_balance_code` columns (e.g., using non-Fannie datasets or custom data)
- Workaround: Ensure feature engineering includes these columns
- Risk: Models trained on synthetic labels will not generalize. Silent fallback hides data quality issues

**Exception Swallowing in Model Factor Extraction:**
- Symptoms: Top factors endpoint returns empty list instead of error when SHAP/feature extraction fails
- Files: `service/model_loader.py` (lines 112, 134-135)
- Trigger: Non-linear models without feature importance, malformed model structure, or numpy shape mismatches
- Workaround: Check returned `top_factors` list length in client code
- Risk: Users receive incomplete scoring responses. No visibility into why factors are missing

**Missing Auth DB Directory on Service Start:**
- Symptoms: First POST to `/auth/register` or `/auth/login` creates `data/auth/` directory if missing
- Files: `service/auth.py` (lines 40-41)
- Trigger: Fresh deployment without `data/auth/` pre-created
- Workaround: None - directory is created on first use
- Risk: Race condition in multi-process deployments (e.g., gunicorn) if multiple workers try to mkdir simultaneously. SQLite may fail to initialize

## Security Considerations

**Weak Default Auth Secret:**
- Risk: `auth_secret` defaults to `"change-me-dev-secret"` in production-like deployments
- Files: `config/settings.py` (line 60)
- Current mitigation: Settings reads from `.env` file
- Recommendations:
  - Require `auth_secret` to be explicitly set (no default)
  - Add validation in `Settings.__init__` to reject development secrets in non-dev environments
  - Document in README that this must be changed before production use
  - Add pre-commit hook to detect commit of `.env` with default secret

**Token Signature Verification Using Shared Secret:**
- Risk: Auth tokens use HMAC-SHA256 with app secret. Token forgery possible if secret is leaked or if application runs multiple instances with different secrets
- Files: `service/auth.py` (lines 81-112)
- Current mitigation: Token includes expiration time
- Recommendations:
  - Add token versioning/key rotation mechanism
  - Consider using asymmetric signing (RS256) if secrets are shared across deployments
  - Validate token issued-at time against server time to detect token manipulation
  - Document that `auth_secret` must be identical across all service instances

**SQLite Database in Plaintext Filesystem:**
- Risk: User credentials stored in SQLite with hashed passwords but DB file is readable by any process with file access
- Files: `service/auth.py` (line 16)
- Current mitigation: PBKDF2-HMAC-SHA256 with 200k iterations for password hashing
- Recommendations:
  - Document that `data/auth/` directory must have restricted permissions (0700)
  - Add startup check to validate DB file permissions
  - Consider encrypting the SQLite database file or moving auth to an external provider
  - Add audit logging for auth events (registration, login attempts, token generation)

**No Rate Limiting on Auth Endpoints:**
- Risk: `/auth/register` and `/auth/login` have no rate limiting. Attackers can brute-force passwords or spam registrations
- Files: `service/api.py` (lines 375-418)
- Current mitigation: None
- Recommendations:
  - Implement per-IP rate limiting on auth endpoints (e.g., 5 attempts per minute)
  - Add login attempt logging/alerting
  - Consider implementing account lockout after N failed attempts
  - Use slowhash library or increase PBKDF2 iterations to slow down brute-force

**Broad HTTP Exception Handling Leaks Implementation Details:**
- Risk: Exception messages are returned directly to clients, may leak internal paths, model names, or system state
- Files: `service/api.py` (lines 509-518, 543-546, 552-555, 587-591)
- Current mitigation: Only in non-production contexts
- Recommendations:
  - Implement exception sanitization layer that logs full details but returns generic messages to clients
  - Use structured error codes instead of exception strings
  - Never include file paths or system details in HTTP responses

**Path Traversal Risk in File-Based Monitoring Results:**
- Risk: Monitoring job output files written to user-specified directory with no path validation
- Files: `service/api.py` (line 194), `main.py` (line 187)
- Current mitigation: `output_dir` is treated as relative path from CWD
- Recommendations:
  - Validate `output_dir` to ensure it's a subdirectory of allowed base (e.g., `reports/`)
  - Reject paths with `..` or absolute paths
  - Use `pathlib.Path.resolve()` and check against whitelist

## Performance Bottlenecks

**Feature DataFrame Memory Expansion in Batch Scoring:**
- Problem: `batch_score()` concatenates all DataFrames into single combined frame before scoring
- Files: `service/model_loader.py` (lines 185-188)
- Cause: Allocates temporary 2x memory for batch operations. For 1000-record batches with 75 features, ~30MB intermediate memory
- Improvement path: Stream records through model in chunks, avoid pandas concat, pre-allocate output arrays

**Prophet Model Loading on Every Forecast Request:**
- Problem: `_get_forecast_model()` only caches loaded models in memory, but Pickle deserialization still occurs
- Files: `service/api.py` (lines 96-101)
- Cause: Even with cache, deserialization of joblib artifacts takes 50-200ms per load
- Improvement path: Keep unpickled model instance in cache, implement model versioning to invalidate cache on new deployments

**Feature Engineering Doesn't Support Incremental Updates:**
- Problem: `features/build_features.py` recomputes all features from raw data on each run
- Cause: No caching of intermediate feature groups (e.g., after macro join)
- Impact: Features command takes 10-20 minutes even for incremental data additions
- Improvement path: Implement feature group checkpointing, incremental join logic for new dates

**Low-Memory Mode Silently Downsample Training Data:**
- Problem: When `low_memory_mode=true` and dataset > 3000 rows, random downsampling occurs without warning
- Files: `training/trainer.py` (lines 441-443)
- Cause: Uses deterministic seed but model quality degradation is silent. No metrics comparing downsampled vs full-size
- Impact: Training AUC/metrics are not comparable across runs
- Improvement path: Log before/after dataset statistics, compute and log quality impact, make threshold configurable per model

## Fragile Areas

**Fannie Mae Ingestion Hard-Coded Column Indices:**
- Files: `data_ingestion/ingest_fannie.py` (lines 62-91)
- Why fragile: Combined loan tape column indices are hard-coded after position 62. Fannie Mae format changes (e.g., new fields added at position 40) will silently corrupt data extraction. No version detection
- Safe modification: Add format version detection at file header, implement versioned column maps, add data quality checks post-extract (e.g., verify credit scores are in expected range)
- Test coverage: `tests/test_ingest_fannie.py` has synthetic test data but doesn't test against real Fannie Mae format changes

**Schema Validation Warnings Are Ignored:**
- Files: `data_ingestion/ingest_fannie.py` (lines 156-171)
- Why fragile: Pandera schema validation failures are logged as warnings but ingestion proceeds. Coerced data may have silent NaN insertions or type mismatches. Second level of exception catching masks root cause
- Safe modification: Fail fast on schema errors unless explicitly allowed via `allow_schema_coercion` flag. Add detailed schema validation reports before proceeding
- Test coverage: No tests verify behavior when schema coercion occurs

**Model Loader Feature Alignment Heuristics:**
- Files: `service/model_loader.py` (lines 40-48, 63-69)
- Why fragile: Feature name/order detection uses multiple fallback strategies (feature_cols list, feature_names_in_, feature_name_). Different model types produce different attribute names. Silent failures return empty list
- Safe modification: Require explicit feature metadata in model artifact, validate at load time, reject models missing feature schema. Add strict mode for production
- Test coverage: `tests/test_model_lifecycle_api.py` tests happy path but not edge cases (models without feature metadata, mismatched feature counts)

**Broad Exception Handlers Hide Real Errors:**
- Files: Multiple locations (see "Tech Debt" section)
- Why fragile: Code catches all exceptions but logs at WARNING level. Unrelated failures (e.g., out of memory, file system errors) are treated same as expected failures
- Safe modification: Use specific exception types, log at ERROR level for unexpected failures, add structured logging context
- Test coverage: Tests generally don't verify exception paths

**In-Memory Cache Without Invalidation Strategy:**
- Files: `service/api.py` (line 52)
- Why fragile: Models can be activated/replaced via `/models/activate` endpoint but forecast cache is not cleared. Old model artifacts may be served until process restart
- Safe modification: Implement cache versioning, add cache invalidation hook in model activation, use weak references for model objects
- Test coverage: No test for cache behavior across model updates

## Scaling Limits

**Job Manager Limited to Single Process:**
- Current capacity: In-memory storage for ~1000 jobs before memory becomes concern
- Limit: Service restart loses all job history. Multiple service instances (load balanced) have independent job registries
- Scaling path: Migrate JobManager to use external backing store (SQLite or Redis), implement distributed job queue (Celery/RQ)

**SQLite Auth Database Not Suitable for High Concurrency:**
- Current capacity: ~100 concurrent connections before contention
- Limit: SQLite uses file-level locks; multiple writers will block. High-frequency token validation queries create bottleneck
- Scaling path: Migrate to PostgreSQL or implement JWT with asymmetric signing to eliminate DB lookups

**Feature Engineering Processes Entire Dataset in Memory:**
- Current capacity: ~2M row Fannie Mae origination fits in ~500MB, but with feature engineering intermediate dataframes, peak memory = ~2GB
- Limit: Datasets > 3GB will OOM on standard cloud VMs. No streaming/chunking support
- Scaling path: Implement Apache Arrow for columnar processing, add Dask for parallel feature engineering, move to data warehouse (DuckDB/ClickHouse)

**Prophet Model Requires Full Dataset in Memory:**
- Current capacity: ~60K unique monthly delinquency time series fits in memory (~1MB)
- Limit: Cannot scale to tens of thousands of time series (e.g., per-state or per-property-type forecasts)
- Scaling path: Use StatsForecast for distributed forecasting, implement hierarchical forecasting, consider external time-series database

## Dependencies at Risk

**Prophet at EOL Planning:**
- Risk: Prophet 1.1.5 is stable but Facebook has reduced maintenance. NumPy 2.0 compatibility required explicit downpin
- Impact: If Prophet becomes unmaintained and NumPy releases breaking changes, cannot upgrade
- Files: `pyproject.toml` (lines 14, 20)
- Migration plan: Monitor Prophet GitHub for deprecation notices. Start evaluating alternatives: `statsmodels.SARIMAX`, `sktime`, `NeuralProphet`, or `darts`

**scikit-learn < 2.0 Constraint:**
- Risk: Pinning scikit-learn to <2.0 due to calibration/interpretability API changes
- Files: `training/calibration.py` (line 27), `pyproject.toml` (line 17)
- Impact: Cannot access scikit-learn 2.0+ security/performance improvements. Will need migration work when upgrading
- Migration plan: Update calibration module to use new CV API, remove `cv='prefit'` workaround

**NumPy < 2.0 Pinning:**
- Risk: Explicit downpin due to Prophet's use of removed `np.float_` type
- Files: `pyproject.toml` (line 14)
- Impact: Cannot access NumPy 2.0 performance improvements and bug fixes
- Migration plan: Either wait for Prophet update or switch forecasting library

**pandera Schema Validation at 0.20.3:**
- Risk: Actively developed but version 0.20 may have performance issues or bugs
- Files: `pyproject.toml` (line 42), `data_ingestion/schema.py`
- Impact: Schema validation failures are silent (logged as warnings), missing coverage means data quality issues propagate
- Migration plan: Evaluate newer pandera versions, consider integrating with Great Expectations for more robust validation

**Plotly/Kaleido for Visualization:**
- Risk: Kaleido 0.2.1 is legacy. Plotly 5.22 still actively maintained but Kaleido development sparse
- Files: `pyproject.toml` (lines 27-28)
- Impact: Static image export may break on new system libraries or Node versions
- Migration plan: Monitor Kaleido maintenance, evaluate alternative export libraries (`selenium`, `playwright`)

## Missing Critical Features

**No Input Validation on API Scoring Endpoints:**
- Problem: Score request features dict accepts any values without schema enforcement
- Blocks: Cannot guarantee model receives expected feature types/ranges. Prevents client-side validation
- Files: `service/schemas.py` (ScoreRequest definition), `service/api.py` (score/batch_score endpoints)

**No Model Versioning or A/B Testing Support:**
- Problem: Only one "active" model can be served. No gradual rollout or shadow mode
- Blocks: Cannot test model changes in production. No mechanism to serve different models to different users
- Files: `service/model_loader.py`, `models/registry.py`

**No Data Quality Validation Pipeline:**
- Problem: Features are computed but never validated against expected distributions
- Blocks: Silent data drift impacts model performance. No early warning before serving bad predictions
- Related: `monitoring/drift.py` exists but only runs offline, not on serving path

**No Automated Model Retraining Triggers:**
- Problem: Models must be retrained manually via `/jobs` endpoints
- Blocks: Cannot set up data drift alerts → retraining → auto-activation pipelines
- Files: `service/jobs.py`, `service/api.py` (job endpoints)

## Test Coverage Gaps

**API Auth Endpoints:**
- What's not tested: Token expiration enforcement, concurrent login attempts, race conditions in user creation, SQLite permission errors
- Files: `service/auth.py`, `service/api.py` (auth routes at lines 375-418)
- Risk: Auth bypass or privilege escalation bugs undetected
- Priority: High

**Model Activation and Cache Invalidation:**
- What's not tested: Forecast cache behavior after model activation, cache consistency across requests, stale model serving
- Files: `service/api.py` (lines 450-461), `service/model_loader.py`
- Risk: Old models served after activation
- Priority: High

**Fannie Mae Ingestion Format Changes:**
- What's not tested: Real Fannie Mae format variations, missing fields, extra fields, malformed rows
- Files: `data_ingestion/ingest_fannie.py`
- Risk: Silent data corruption on real data
- Priority: High

**Low-Memory Mode and Downsampling:**
- What's not tested: Actual memory usage under load, downsampling impact on model quality, comparison of downsampled vs full models
- Files: `training/trainer.py` (lines 441-443)
- Risk: Silent quality degradation
- Priority: Medium

**Exception Paths in Model Scoring:**
- What's not tested: Model missing required features, NaN/inf propagation, batch scoring with heterogeneous input
- Files: `service/model_loader.py` (_predict_proba, _top_factors methods)
- Risk: Production errors undetected
- Priority: Medium

**Monitoring Job Drift Detection:**
- What's not tested: Missing columns in reference/current data, all-NaN features, categorical drift on numeric-only logic
- Files: `monitoring/drift.py`, `monitoring/score_drift.py`
- Risk: Monitoring job crashes silently or produces misleading results
- Priority: Medium

---

*Concerns audit: 2026-03-12*

# UI Operator Runbook

This is the practical, step-by-step guide for running the system from the web UI.

## 1. Start the app

```bash
python -m main serve
```

Open:

- `http://localhost:8000/` (operations UI)

## 2. Pre-flight checks in UI

In the top cards:

1. Confirm **API badge** shows `ok`.
2. Confirm **System Snapshot** loads metadata.
3. Check **mode**:
   - `demo`: no local Fannie raw files detected.
   - `real-data`: raw files detected under `data/raw/fannie_mae/...`.

## 2b. Choose mode

- **Demo mode**: do nothing; continue without login.
- **Private user mode**:
  1. Use **User Login (Private Modeling)** card.
  2. Register username/password once.
  3. Login.
  4. Subsequent Jobs/Models actions are isolated to your user namespace.

## 3. Seed demo data (Render / ephemeral deploys)

Use the **Background Jobs** panel:

1. Set **Job Type** = `seed-demo`.
2. Use payload:

```json
{
  "output_dir": "data/raw/fannie_mae/combined",
  "filename": "demo_2025Q1.csv",
  "n_loans": 120,
  "months": 6,
  "seed": 42,
  "overwrite": true
}
```

3. Submit and wait for `succeeded`.

## 4. Build data + train model

Use the **Background Jobs** panel:

1. Set **Job Type** = `pipeline`.
2. Use payload:

```json
{
  "source": "fannie-mae",
  "model": "sklearn-logreg"
}
```

3. Submit.
4. Wait for status `succeeded` in the jobs output.

If it fails with missing raw files, place files here and rerun:

- `data/raw/fannie_mae/origination/Acquisition_*.txt`
- `data/raw/fannie_mae/performance/Performance_*.txt`

## 5. Train only (after features exist)

Use **Background Jobs**:

1. Set **Job Type** = `train`.
2. Payload:

```json
{
  "model": "sklearn-rf"
}
```

3. Submit and wait for terminal status.

## 6. Activate model for scoring

Use **Model Lifecycle** panel:

1. Click **Refresh Models**.
2. Pick model name (example: `sklearn-rf`).
3. Leave Version ID blank to activate latest, or paste a specific version.
4. Click **Activate Model**.

Expected:

- Response with `name`, `version_id`, and `current_alias_path`.
- Scoring service can use `current.joblib`.

## 7. Run scoring from UI

### Single score

Use **Single Loan Score**:

1. Keep default JSON or paste your own feature object.
2. Submit.
3. Expect `pd`, `decision`, and `top_factors`.

### Batch score

Use **Batch Score**:

1. Paste an array of score records.
2. Submit.
3. Expect `results[]` and `count`.

## 8. Run forecast

Use **Forecast**:

1. `source`: `fannie-mae`
2. `horizon`: e.g. `24`
3. Submit.

Expected:

- Forecast rows with `ds`, `yhat`, `yhat_lower`, `yhat_upper`.

If you get artifact-not-found, run a `train` job with model `prophet` first.

## 9. Run monitoring

Use **Background Jobs** with `monitor` payload:

```json
{
  "reference_path": "data/processed/fannie_mae/features/features.parquet",
  "current_path": "data/processed/fannie_mae/features/current_period.parquet",
  "output_dir": "reports/monitoring"
}
```

After success:

- **Monitoring Summary** card updates from `reports/monitoring/summary.md`.

## 10. Common failure patterns

### Train job fails: feature parquet missing

Run `pipeline` first, then rerun `train`.

### Pipeline fails: no raw files found

Add Fannie raw files to `data/raw/fannie_mae/...`, then retry.

### Scoring returns model not loaded

Activate a model in **Model Lifecycle** and retry.

### Forecast returns artifact not found

Run `train` with model `prophet`.

## 11. Quick acceptance checklist

1. Pipeline job succeeds.
2. Seed-demo job succeeds (for Render demo environments).
2. Train job succeeds.
3. Model activation succeeds.
4. Single score returns `pd`.
5. Batch score returns `count`.
6. Forecast returns `forecast[]`.
7. Monitor job succeeds and summary appears.

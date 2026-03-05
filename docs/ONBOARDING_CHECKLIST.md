# Onboarding Checklist

Use this checklist for a first successful run via the UI.

## Pre-Req

- [ ] Python 3.11 environment is active
- [ ] Dependencies installed: `pip install -e ".[dev]"`
- [ ] App starts: `python -m main serve`
- [ ] UI opens at `http://localhost:8000/`

## Baseline Health

- [ ] `GET /health` returns `status: ok`
- [ ] `GET /metadata` returns app/version/mode
- [ ] Jobs panel renders without errors
- [ ] Model Lifecycle panel renders without errors

## Optional Private User Mode

- [ ] Register via UI auth card
- [ ] Login succeeds and username is shown
- [ ] Submit `/me` train job from UI (auto-routed when logged in)

## Data + Training

- [ ] Submit `pipeline` job from UI (source `fannie-mae`, model `sklearn-rf`)
- [ ] Job reaches `succeeded`
- [ ] Submit `train` job (model `sklearn-rf`)
- [ ] Job reaches `succeeded`

## Model Activation

- [ ] Click **Refresh Models**
- [ ] Confirm at least one version exists
- [ ] Activate latest model
- [ ] `GET /models/active` returns selected version

## Inference

- [ ] Single score returns `pd` + `decision`
- [ ] Batch score returns `count` + `results[]`
- [ ] Forecast returns `forecast[]`

## Monitoring

- [ ] Submit `monitor` job with valid parquet paths
- [ ] Job reaches `succeeded`
- [ ] Monitoring Summary card shows latest report

## Ops Readiness

- [ ] `GET /ready` returns `200` with `status: ready`
- [ ] `bash scripts/golden_path.sh` completes

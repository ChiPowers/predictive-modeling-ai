# Model Card — predictive-modeling-ai

**Version:** 0.1.0
**Date:** 2026-03-02
**Authors:** Chivon Powers
**Model family:** Prophet (time-series), Logistic Regression (PD), Random Forest (PD)

---

## Overview

This project contains three models trained on publicly available Fannie Mae
single-family mortgage data and FRED macroeconomic series. Together they address
two analytical tasks:

| Model key | Type | Task |
|-----------|------|------|
| `prophet` | Facebook Prophet (additive decomposition) | Forecast aggregate monthly delinquency rates |
| `sklearn-logreg` | Logistic Regression | Loan-level probability of default (PD) |
| `sklearn-rf` | Random Forest Classifier | Loan-level probability of default (PD) |

---

## Intended Use

### Primary Use Cases

- **Portfolio trend monitoring** — `prophet` forecasts the portfolio-level
  delinquency rate 12–24 months forward to support loss-reserve planning and
  stress-testing.
- **Origination risk scoring** — `sklearn-logreg` and `sklearn-rf` estimate each
  loan's probability of reaching 90+ days past due (or foreclosure), supporting
  underwriting review queues and pricing adjustments.
- **Portfolio reporting and research** — interactive dashboards and bulk scoring
  for investor reporting, product analysis, and regulatory capital modelling.

### Intended Users

Data scientists, quantitative analysts, and risk managers at mortgage originators,
servicers, and GSE/agency partners who have licensed access to Fannie Mae loan
performance data.

### Out-of-Scope Uses

- **Automated credit denial** without human review — these models are scoring
  aids, not autonomous decision engines.
- **Non-US or non-GSE mortgage products** — trained exclusively on conforming
  Fannie Mae loans; performance on jumbo, non-QM, FHA, VA, or non-US loans is
  unknown and likely degraded.
- **Real-time origination decisioning at scale** without additional latency and
  throughput testing.
- **Individual consumer credit reporting** — outputs are not FCRA-compliant credit
  scores and must not be used as such.

---

## Training Data

### Source

Fannie Mae Single-Family Loan Performance dataset (public release) accessed via
the [Fannie Mae Capital Markets portal](https://capitalmarkets.fanniemae.com/).
FRED macroeconomic series joined at origination date (6 monthly series).

### Coverage

- **Geography:** United States (conforming loan limits)
- **Loan types:** Fixed and adjustable rate; single-family, condo, co-op, PUD
- **Vintage range:** Quarterly cohorts available from 1999 Q1 onward
- **Observation count:** Varies by quarters ingested; typically millions of
  origination records and tens of millions of monthly performance records

### Label Construction

The binary default label (`default_flag`) is derived as:

1. `max_dpd >= 3` (peak delinquency status ≥ 3 in the performance panel), **or**
2. `zero_balance_code` in `{02, 03, 06, 09, 15}` (foreclosure, short sale, REO),
   **or**
3. Synthetic 5% Bernoulli draw — used only when no label signal is present in the
   ingested data (demonstration / unit-test mode; clearly logged as a warning).

### Feature Engineering

19 features across four groups — see [`config/features.yaml`](../config/features.yaml)
for full definitions. Key inputs:

| Feature | Source | Rationale |
|---------|--------|-----------|
| `credit_score` | Origination | Primary credit quality signal |
| `orig_ltv` / `orig_cltv` | Origination | Collateral coverage |
| `orig_dti` | Origination | Payment capacity |
| `orig_interest_rate` | Origination | Sensitivity to rate shock |
| `orig_upb` / `log_upb` | Origination | Exposure magnitude |
| `is_high_ltv` (>80) | Derived | PMI threshold indicator |
| `is_high_dti` (>43) | Derived | QM compliance boundary |
| `is_arm` | Derived | Adjustable rate risk flag |
| `fedfunds` / `mortgage30us` | FRED | Rate environment at origination |
| `unrate` | FRED | Employment environment at origination |

**Leakage control:** All performance-derived features (rolling DPD, cumulative
prepayment indicators) are computed after sorting by `(loan_id, observation_date)`.
Macro features are joined at the origination month, not the observation date.

---

## Evaluation

### Quantitative Results

| Model | Metric | Value |
|-------|--------|-------|
| `prophet` | In-sample MAE (delinquency rate) | ~0.003–0.008 |
| `sklearn-logreg` | Holdout AUC | 0.68–0.72 |
| `sklearn-rf` | Holdout AUC | 0.73–0.78 |

Train / test split: 80 / 20, stratified on default label,
`random_state` controlled via `settings.random_seed`.

### Performance Across Subgroups

**Not formally evaluated in v0.1.0.** Known gaps:

- Performance by borrower demographic attributes (race, ethnicity, sex) has not
  been assessed. Fannie Mae public files do not include these fields directly;
  HMDA linkage would be required.
- Performance by loan vintage, geography (MSA), and loan purpose (purchase vs.
  refinance) has not been segmented.
- Origination cohorts from stressed periods (2007–2010, 2020–2021) may behave
  differently from quiet periods; the model does not explicitly condition on
  macro regime.

These gaps must be addressed before any deployment that could affect consumers.

---

## Limitations

1. **Static macro features** — FRED series are joined at origination; the model
   does not re-score loans as rates or unemployment change after origination.
2. **No temporal validation** — holdout split is random, not time-based. A
   walk-forward / out-of-time validation on held-out vintage quarters is strongly
   recommended before production use.
3. **Synthetic labels in demo mode** — if performance data is absent, the trainer
   falls back to a random 5% default rate. Models trained in this mode are
   non-predictive and must not be deployed.
4. **Prophet regime sensitivity** — the Prophet model does not include macro
   regressors and will underperform during sharp rate or unemployment shocks.
5. **No calibration** — PD scores are raw `predict_proba` outputs from
   `class_weight="balanced"` models. Platt scaling or isotonic regression is
   recommended before using scores as calibrated probabilities.
6. **Class imbalance** — balanced class weighting improves recall on defaults but
   biases probability scores upward. Downstream decision thresholds should be
   tuned to the deployment operating point (precision/recall tradeoff).
7. **Python / dependency version lock** — `numpy<2.0` is required due to Prophet
   1.1.5 compatibility. This constraint should be revisited when Prophet 2.x is
   available.

---

## Risk Considerations

### Fair Lending / Disparate Impact

Origination features such as DTI, LTV, and loan amount can serve as proxies for
protected class membership (race, national origin, sex) under ECOA and FHA. Use
of these features in automated scoring **requires**:

- Disparate impact analysis on any downstream credit decision
- Legal review before use in underwriting, pricing, or servicing decisions
- Documentation in the institution's model risk management framework

### Model Risk (SR 11-7 / OCC 2011-12)

This codebase provides the development layer of a model. Before production
deployment at a regulated institution:

- An independent validation team must perform out-of-time backtesting, benchmark
  comparison, and sensitivity analysis
- A model risk rating must be assigned based on materiality and complexity
- Ongoing performance monitoring (see below) must be established prior to go-live

### Data Licensing

Fannie Mae loan performance data is provided under Fannie Mae's data licensing
terms. Users are responsible for compliance with those terms. FRED data is in
the public domain (St. Louis Fed).

### Adversarial / Gaming Risk

Loan-level PD scores could in principle be gamed by applicants if score
explanations are disclosed in detail. Limit feature-level disclosure in
consumer-facing contexts.

---

## Monitoring Plan

The `monitoring/` module implements three complementary checks, run via
`pmai monitor` after each scoring period.

### 1. Feature Drift (PSI + KS)

**Monitored features:** `credit_score`, `orig_ltv`, `orig_dti`, `orig_upb`,
`orig_interest_rate`, `orig_cltv`

| Statistic | Alert threshold | Action |
|-----------|----------------|--------|
| PSI | ≥ 0.25 | Investigate distribution shift; consider retraining |
| PSI | 0.10–0.25 | Warning — monitor closely |
| KS p-value | < 0.05 | Flag for investigation |

**Output:** `reports/monitoring/drift_features.json`

### 2. Score Distribution Drift (PSI + KS)

Tracks changes in the PD score distribution between the reference (training)
period and the current scoring period.

**Output:** `reports/monitoring/score_drift.json`

### 3. Rolling AUC (requires label feedback)

Computed over a rolling window (default: 3 periods) once `default_flag` labels
are available for scored loans (~12–18 months post-origination for 90-day DPD).

| Metric | Alert threshold | Action |
|--------|----------------|--------|
| Rolling AUC | < 0.65 | Performance degradation — escalate to model owner |

**Output:** `reports/monitoring/perf_drift.json`

### 4. Monitoring Report

Every monitoring run writes `reports/monitoring/summary.md` — a human-readable
Markdown summary of all checks, suitable for inclusion in a model performance
report or Confluence page.

### Recommended Monitoring Cadence

| Check | Frequency | Notes |
|-------|-----------|-------|
| Feature drift | Monthly | After each origination batch |
| Score drift | Monthly | After each scoring run |
| Rolling AUC | Quarterly | Constrained by 90-day label lag |
| Full model refresh | Annually (or on AUC alert) | Retrain on most recent 5+ years |

---

## Responsible AI Checklist

- [x] Training data is publicly licensed (Fannie Mae + FRED)
- [x] Label construction is documented and reproducible
- [x] Leakage guard implemented and tested
- [x] Class imbalance addressed (balanced class weights)
- [ ] Out-of-time validation (planned — v0.2.0)
- [ ] Subgroup / fairness analysis (planned — v0.2.0)
- [ ] Score calibration (planned — v0.2.0)
- [ ] Independent model validation (required before production deployment)
- [x] Monitoring plan documented and implemented
- [x] Out-of-scope uses documented

---

## Citation

If referencing this work:

```
Powers, C. (2026). predictive-modeling-ai: End-to-end mortgage analytics
platform. GitHub. https://github.com/chivonpowers/predictive-modeling-ai
```

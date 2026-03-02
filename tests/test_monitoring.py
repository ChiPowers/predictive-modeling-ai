"""Tests for monitoring modules: drift, score_drift, perf_drift."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def stable_series() -> tuple[pd.Series, pd.Series]:
    """Two i.i.d. normal samples — should show no drift."""
    rng = np.random.default_rng(0)
    ref = pd.Series(rng.normal(700, 50, 2000))
    cur = pd.Series(rng.normal(700, 50, 2000))
    return ref, cur


@pytest.fixture()
def drifted_series() -> tuple[pd.Series, pd.Series]:
    """Reference and significantly shifted current — should trigger alert."""
    rng = np.random.default_rng(1)
    ref = pd.Series(rng.normal(700, 50, 2000))
    cur = pd.Series(rng.normal(550, 80, 2000))  # large mean + std shift
    return ref, cur


@pytest.fixture()
def stable_origination_dfs() -> tuple[pd.DataFrame, pd.DataFrame]:
    rng = np.random.default_rng(2)
    n = 500
    data = {
        "credit_score": rng.normal(720, 40, n),
        "orig_ltv": rng.uniform(50, 95, n),
        "orig_dti": rng.uniform(20, 45, n),
        "orig_upb": rng.normal(300_000, 80_000, n),
        "orig_interest_rate": rng.uniform(3, 7, n),
        "orig_cltv": rng.uniform(50, 100, n),
    }
    ref = pd.DataFrame(data)
    cur = pd.DataFrame({k: v + rng.normal(0, 1, n) for k, v in data.items()})
    return ref, cur


@pytest.fixture()
def perf_data() -> tuple[pd.Series, pd.Series, pd.Series]:
    """Binary labels, PD scores, and period column for rolling AUC tests."""
    rng = np.random.default_rng(3)
    n = 600
    periods = np.repeat(["2023-01", "2023-02", "2023-03", "2023-04", "2023-05", "2023-06"], 100)
    scores = rng.beta(2, 8, n)  # right-skewed, like a well-calibrated PD model
    labels = (scores + rng.normal(0, 0.15, n) > 0.35).astype(int)
    return pd.Series(labels), pd.Series(scores), pd.Series(periods)


# ---------------------------------------------------------------------------
# drift.py — PSI
# ---------------------------------------------------------------------------


class TestPSI:
    def test_identical_distributions_near_zero(self, stable_series: tuple[pd.Series, pd.Series]) -> None:
        from monitoring.drift import psi

        ref, cur = stable_series
        val = psi(ref, cur)
        assert val < 0.10, f"Expected PSI < 0.10 for similar distributions, got {val:.4f}"

    def test_shifted_distribution_triggers_alert(
        self, drifted_series: tuple[pd.Series, pd.Series]
    ) -> None:
        from monitoring.drift import psi

        ref, cur = drifted_series
        val = psi(ref, cur)
        assert val >= 0.25, f"Expected PSI >= 0.25 for drifted distributions, got {val:.4f}"

    def test_empty_series_returns_zero(self) -> None:
        from monitoring.drift import psi

        val = psi(pd.Series([], dtype=float), pd.Series([], dtype=float))
        assert val == 0.0

    def test_nan_values_handled(self) -> None:
        from monitoring.drift import psi

        ref = pd.Series([1.0, 2.0, float("nan"), 3.0])
        cur = pd.Series([1.1, 2.1, float("nan"), 3.1])
        val = psi(ref, cur)
        assert val >= 0.0


# ---------------------------------------------------------------------------
# drift.py — KS test
# ---------------------------------------------------------------------------


class TestKSTest:
    def test_same_distribution_high_pvalue(self, stable_series: tuple[pd.Series, pd.Series]) -> None:
        from monitoring.drift import ks_test

        ref, cur = stable_series
        result = ks_test(ref, cur)
        assert result["p_value"] > 0.05, "Stable distributions should not reject H0"

    def test_shifted_distribution_low_pvalue(
        self, drifted_series: tuple[pd.Series, pd.Series]
    ) -> None:
        from monitoring.drift import ks_test

        ref, cur = drifted_series
        result = ks_test(ref, cur)
        assert result["p_value"] < 0.05

    def test_output_keys(self, stable_series: tuple[pd.Series, pd.Series]) -> None:
        from monitoring.drift import ks_test

        ref, cur = stable_series
        result = ks_test(ref, cur)
        assert "statistic" in result
        assert "p_value" in result


# ---------------------------------------------------------------------------
# drift.py — run_feature_drift
# ---------------------------------------------------------------------------


class TestRunFeatureDrift:
    def test_returns_result_for_each_feature(
        self, stable_origination_dfs: tuple[pd.DataFrame, pd.DataFrame]
    ) -> None:
        from monitoring.drift import KEY_NUMERIC_FEATURES, run_feature_drift

        ref, cur = stable_origination_dfs
        results = run_feature_drift(ref, cur)
        for feat in KEY_NUMERIC_FEATURES:
            assert feat in results

    def test_result_schema(
        self, stable_origination_dfs: tuple[pd.DataFrame, pd.DataFrame]
    ) -> None:
        from monitoring.drift import run_feature_drift

        ref, cur = stable_origination_dfs
        results = run_feature_drift(ref, cur)
        for data in results.values():
            assert "psi" in data
            assert "ks_statistic" in data
            assert "ks_p_value" in data
            assert "severity" in data
            assert "alert" in data

    def test_missing_feature_skipped(self) -> None:
        from monitoring.drift import run_feature_drift

        ref = pd.DataFrame({"credit_score": [700, 720, 680]})
        cur = pd.DataFrame({"credit_score": [710, 730, 690]})
        results = run_feature_drift(ref, cur, features=["credit_score", "orig_ltv"])
        assert "credit_score" in results
        assert "orig_ltv" not in results

    def test_writes_json(
        self,
        tmp_path: Path,
        stable_origination_dfs: tuple[pd.DataFrame, pd.DataFrame],
    ) -> None:
        from monitoring.drift import run_feature_drift

        ref, cur = stable_origination_dfs
        run_feature_drift(ref, cur, output_dir=tmp_path)
        out = tmp_path / "drift_features.json"
        assert out.exists()
        data = json.loads(out.read_text())
        assert isinstance(data, dict)


# ---------------------------------------------------------------------------
# score_drift.py — run_score_drift
# ---------------------------------------------------------------------------


class TestRunScoreDrift:
    def test_stable_no_alert(self, stable_series: tuple[pd.Series, pd.Series]) -> None:
        from monitoring.score_drift import run_score_drift

        ref, cur = stable_series
        # Normalise both using ref stats so the scaling doesn't introduce drift
        mn, mx = ref.min(), ref.max()
        result = run_score_drift((ref - mn) / (mx - mn), (cur - mn) / (mx - mn))
        assert result["severity"] in ("ok", "warning")

    def test_drifted_triggers_alert(self, drifted_series: tuple[pd.Series, pd.Series]) -> None:
        from monitoring.score_drift import run_score_drift

        ref, cur = drifted_series
        result = run_score_drift(ref, cur)
        assert result["alert"] is True

    def test_output_schema(self, stable_series: tuple[pd.Series, pd.Series]) -> None:
        from monitoring.score_drift import run_score_drift

        ref, cur = stable_series
        result = run_score_drift(ref, cur)
        expected_keys = {
            "psi", "ks_statistic", "ks_p_value",
            "reference_percentiles", "current_percentiles",
            "mean_shift", "severity", "alert",
        }
        assert expected_keys.issubset(result.keys())

    def test_percentiles_present(self, stable_series: tuple[pd.Series, pd.Series]) -> None:
        from monitoring.score_drift import run_score_drift

        ref, cur = stable_series
        result = run_score_drift(ref, cur)
        for key in ["p10", "p25", "p50", "p75", "p90"]:
            assert key in result["reference_percentiles"]
            assert key in result["current_percentiles"]

    def test_writes_json(
        self, tmp_path: Path, stable_series: tuple[pd.Series, pd.Series]
    ) -> None:
        from monitoring.score_drift import run_score_drift

        ref, cur = stable_series
        run_score_drift(ref, cur, output_dir=tmp_path)
        assert (tmp_path / "score_drift.json").exists()


# ---------------------------------------------------------------------------
# perf_drift.py — rolling_auc / run_perf_drift
# ---------------------------------------------------------------------------


class TestRollingAUC:
    def test_returns_one_row_per_period(
        self, perf_data: tuple[pd.Series, pd.Series, pd.Series]
    ) -> None:
        from monitoring.perf_drift import rolling_auc

        labels, scores, periods = perf_data
        result = rolling_auc(labels, scores, periods, window=3)
        assert len(result) == periods.nunique()

    def test_auc_in_valid_range(
        self, perf_data: tuple[pd.Series, pd.Series, pd.Series]
    ) -> None:
        from monitoring.perf_drift import rolling_auc

        labels, scores, periods = perf_data
        result = rolling_auc(labels, scores, periods)
        valid = result["auc"].dropna()
        assert ((valid >= 0.0) & (valid <= 1.0)).all()

    def test_single_class_auc_is_none(self) -> None:
        from monitoring.perf_drift import rolling_auc

        labels = pd.Series([0, 0, 0, 0])
        scores = pd.Series([0.1, 0.2, 0.1, 0.3])
        periods = pd.Series(["2023-01"] * 4)
        result = rolling_auc(labels, scores, periods)
        assert result["auc"].iloc[0] is None


class TestRunPerfDrift:
    def test_output_schema(
        self, perf_data: tuple[pd.Series, pd.Series, pd.Series]
    ) -> None:
        from monitoring.perf_drift import run_perf_drift

        labels, scores, periods = perf_data
        result = run_perf_drift(labels, scores, periods)
        assert "rolling_auc" in result
        assert "latest_auc" in result
        assert "trend" in result
        assert "alert" in result

    def test_above_threshold_no_alert(
        self, perf_data: tuple[pd.Series, pd.Series, pd.Series]
    ) -> None:
        from monitoring.perf_drift import run_perf_drift

        labels, scores, periods = perf_data
        result = run_perf_drift(labels, scores, periods, auc_alert_threshold=0.0)
        assert result["alert"] is False

    def test_below_threshold_alert(
        self, perf_data: tuple[pd.Series, pd.Series, pd.Series]
    ) -> None:
        from monitoring.perf_drift import run_perf_drift

        labels, scores, periods = perf_data
        result = run_perf_drift(labels, scores, periods, auc_alert_threshold=1.0)
        assert result["alert"] is True

    def test_writes_json(
        self, tmp_path: Path, perf_data: tuple[pd.Series, pd.Series, pd.Series]
    ) -> None:
        from monitoring.perf_drift import run_perf_drift

        labels, scores, periods = perf_data
        run_perf_drift(labels, scores, periods, output_dir=tmp_path)
        assert (tmp_path / "perf_drift.json").exists()


# ---------------------------------------------------------------------------
# monitoring/__init__.py — write_summary_report
# ---------------------------------------------------------------------------


class TestWriteSummaryReport:
    def test_creates_summary_md(self, tmp_path: Path) -> None:
        from monitoring import write_summary_report

        results = {
            "feature_drift": {
                "credit_score": {
                    "psi": 0.05,
                    "ks_statistic": 0.03,
                    "ks_p_value": 0.45,
                    "severity": "ok",
                    "alert": False,
                }
            },
            "score_drift": {
                "psi": 0.08,
                "ks_statistic": 0.04,
                "ks_p_value": 0.30,
                "reference_percentiles": {"p10": 0.1, "p25": 0.2, "p50": 0.3, "p75": 0.4, "p90": 0.5},
                "current_percentiles": {"p10": 0.11, "p25": 0.21, "p50": 0.31, "p75": 0.41, "p90": 0.51},
                "mean_shift": 0.01,
                "severity": "ok",
                "alert": False,
            },
            "perf_drift": None,
        }
        path = write_summary_report(results, tmp_path)
        assert path.exists()
        content = path.read_text()
        assert "# Monitoring Summary" in content
        assert "credit_score" in content
        assert "Labels not yet available" in content

    def test_alert_appears_in_summary(self, tmp_path: Path) -> None:
        from monitoring import write_summary_report

        results = {
            "feature_drift": {
                "credit_score": {
                    "psi": 0.30,
                    "ks_statistic": 0.20,
                    "ks_p_value": 0.001,
                    "severity": "alert",
                    "alert": True,
                }
            },
            "score_drift": {},
            "perf_drift": None,
        }
        path = write_summary_report(results, tmp_path)
        content = path.read_text()
        assert "ALERT" in content
        assert "## Alerts" in content

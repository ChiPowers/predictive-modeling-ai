"""Tests for training/calibration.py."""
from __future__ import annotations

import numpy as np
import pytest
from sklearn.datasets import make_classification
from sklearn.linear_model import LogisticRegression


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _fitted_model(n: int = 300, seed: int = 0):
    X, y = make_classification(n_samples=n, n_features=10, random_state=seed)
    model = LogisticRegression(random_state=seed)
    model.fit(X[: n // 2], y[: n // 2])
    return model, X[n // 2 :], y[n // 2 :]


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_calibrate_returns_model_with_predict_proba():
    from training.calibration import calibrate

    model, X_val, y_val = _fitted_model()
    cal = calibrate(model, X_val, y_val, method="isotonic")

    assert hasattr(cal, "predict_proba"), "Calibrated model must have predict_proba"
    probs = cal.predict_proba(X_val)
    assert probs.shape == (len(X_val), 2)
    np.testing.assert_allclose(probs.sum(axis=1), 1.0, atol=1e-6)


def test_calibrate_sigmoid():
    from training.calibration import calibrate

    model, X_val, y_val = _fitted_model()
    cal = calibrate(model, X_val, y_val, method="sigmoid")
    assert hasattr(cal, "predict_proba")


def test_ece_decreases_or_stays_flat():
    """ECE after calibration should not be worse than before by a large margin."""
    from training.calibration import calibrate, _ece

    model, X_val, y_val = _fitted_model()
    cal = calibrate(model, X_val, y_val, method="isotonic")

    y_arr = np.asarray(y_val)
    ece_before = _ece(y_arr, model.predict_proba(X_val)[:, 1])
    ece_after = _ece(y_arr, cal.predict_proba(X_val)[:, 1])

    # Allow a tiny tolerance — isotonic fitting on the same set shouldn't inflate ECE
    assert ece_after <= ece_before + 0.05, (
        f"ECE worsened significantly: before={ece_before:.4f} after={ece_after:.4f}"
    )

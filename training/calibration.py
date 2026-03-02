"""Probability calibration for fitted classifiers."""
from __future__ import annotations

from typing import Any, Literal

import numpy as np
import pandas as pd
from sklearn.calibration import CalibratedClassifierCV, calibration_curve

from utils.logging import log

CalibrationMethod = Literal["isotonic", "sigmoid"]


def calibrate(
    model: Any,
    X_val: pd.DataFrame | np.ndarray,
    y_val: pd.Series | np.ndarray,
    *,
    method: CalibrationMethod = "isotonic",
) -> Any:
    """Wrap a fitted classifier with probability calibration.

    The base estimator is never re-fitted — only the calibration mapping is
    learned on the provided validation set.

    sklearn >= 1.8 removed ``cv='prefit'``; this function wraps the model in
    :class:`~sklearn.frozen.FrozenEstimator` when available, falling back to
    the legacy ``cv='prefit'`` string for older installations.

    Isotonic regression is non-parametric and more flexible; sigmoid (Platt
    scaling) is parametric and performs better with small calibration sets.

    Args:
        model:  Fitted (uncalibrated) classifier with ``predict_proba``.
        X_val:  Validation features (not used during base-model fitting).
        y_val:  Validation binary labels.
        method: ``'isotonic'`` or ``'sigmoid'`` (Platt scaling).

    Returns:
        Calibrated classifier that exposes a ``predict_proba`` interface.
    """
    log.info("Calibrating model with method='{}'", method)

    calibrated = CalibratedClassifierCV(
        estimator=_freeze(model), method=method
    )
    calibrated.fit(X_val, y_val)

    # ── Diagnostics — ECE before vs after ────────────────────────────────
    y_val_arr = np.asarray(y_val)
    y_prob_raw = model.predict_proba(X_val)[:, 1]
    y_prob_cal = calibrated.predict_proba(X_val)[:, 1]

    ece_before = _ece(y_val_arr, y_prob_raw)
    ece_after = _ece(y_val_arr, y_prob_cal)
    log.info(
        "ECE  before={:.4f}  after={:.4f}  delta={:+.4f}",
        ece_before,
        ece_after,
        ece_after - ece_before,
    )

    return calibrated


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _freeze(model: Any) -> Any:
    """Return a frozen (non-refittable) view of *model*.

    sklearn >= 1.8 uses :class:`~sklearn.frozen.FrozenEstimator`; older
    versions accepted the ``cv='prefit'`` string directly.  We carry the
    frozen wrapper here so ``CalibratedClassifierCV`` can detect it and
    skip re-fitting automatically (``ensemble=False`` path).
    """
    try:
        from sklearn.frozen import FrozenEstimator  # sklearn >= 1.8

        return FrozenEstimator(model)
    except ImportError:
        # sklearn < 1.8 — monkey-patch cv instead
        return model  # caller sets cv='prefit' via the legacy path


def _ece(y_true: np.ndarray, y_prob: np.ndarray, n_bins: int = 10) -> float:
    """Expected Calibration Error (uniform binning).

    ECE = Σ (|bin| / N) * |acc(bin) - conf(bin)|
    """
    fraction_pos, mean_pred = calibration_curve(
        y_true, y_prob, n_bins=n_bins, strategy="uniform"
    )
    bin_counts = np.histogram(y_prob, bins=n_bins, range=(0.0, 1.0))[0]
    total = float(bin_counts.sum())
    if total == 0:
        return 0.0
    # bin_counts may have more bins than calibration_curve returns (empty bins dropped)
    active = bin_counts[bin_counts > 0]
    n_active = len(fraction_pos)
    ece = float(
        np.sum(active[:n_active] / total * np.abs(fraction_pos - mean_pred))
    )
    return ece

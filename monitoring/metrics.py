"""Model monitoring — track prediction quality and data drift."""
from __future__ import annotations

import pandas as pd

from utils.logging import log


def log_prediction_error(
    y_true: pd.Series,
    y_pred: pd.Series,
    model: str,
    source: str,
) -> dict[str, float]:
    """Compute and log standard regression error metrics.

    Args:
        y_true: Observed actuals.
        y_pred: Model predictions.
        model:  Model identifier.
        source: Dataset source key.

    Returns:
        Dict with mae, rmse, mape keys.
    """
    import numpy as np

    mae = float(np.abs(y_true - y_pred).mean())
    rmse = float(np.sqrt(((y_true - y_pred) ** 2).mean()))
    mape = float((np.abs((y_true - y_pred) / y_true.replace(0, float("nan")))).mean()) * 100

    metrics = {"mae": mae, "rmse": rmse, "mape": mape}
    log.info("Metrics [model={} source={}]: {}", model, source, metrics)
    return metrics

"""SHAP-based model interpretability — feature importance and explanation plots."""
from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from utils.logging import log

FIGURES_DIR = Path("reports") / "figures"


def explain(
    model: Any,
    X_background: pd.DataFrame | np.ndarray[Any, np.dtype[Any]],
    X_explain: pd.DataFrame | np.ndarray[Any, np.dtype[Any]],
    *,
    feature_names: list[str] | None = None,
    max_display: int = 20,
) -> dict[str, float]:
    """Compute SHAP values and write summary plots to ``reports/figures/``.

    Uses :class:`shap.TreeExplainer` for tree-based models (XGBoost,
    LightGBM, sklearn forests).  Falls back to
    :class:`shap.PermutationExplainer` when the model has no accessible
    tree structure (e.g., calibrated wrappers).

    Saves:
        * ``reports/figures/shap_summary.png`` — beeswarm plot (value + direction)
        * ``reports/figures/shap_bar.png`` — mean |SHAP| bar chart

    Args:
        model:         Fitted model (or calibrated wrapper).
        X_background:  Background dataset used to initialise the explainer.
                       A sub-sample of ~200–500 rows is sufficient.
        X_explain:     Observations to explain.  Use a representative
                       sub-sample for speed (e.g., 1 000 rows).
        feature_names: Column labels.  Inferred from a DataFrame automatically.
        max_display:   Maximum features shown in each plot.

    Returns:
        Dict mapping every feature name to its mean absolute SHAP value.
    """
    import matplotlib
    matplotlib.use("Agg")  # headless — no display required

    # ── Resolve feature names ─────────────────────────────────────────────
    if feature_names is None and isinstance(X_explain, pd.DataFrame):
        feature_names = list(X_explain.columns)

    X_bg = _to_array(X_background)
    X_ex = _to_array(X_explain)

    log.info(
        "Computing SHAP values — background={} explain={}", X_bg.shape, X_ex.shape
    )

    # ── Build explainer ───────────────────────────────────────────────────
    explainer = _build_explainer(model, X_bg)

    # ── Compute SHAP values ───────────────────────────────────────────────
    shap_values = explainer(X_ex)

    # For binary classifiers, SHAP may return shape (n, p, 2); keep class-1 slice
    if hasattr(shap_values, "values") and shap_values.values.ndim == 3:
        sv = shap_values[..., 1]
    else:
        sv = shap_values

    FIGURES_DIR.mkdir(parents=True, exist_ok=True)

    _save_summary(sv, X_ex, feature_names, max_display)
    mean_abs = _save_bar(sv, feature_names, max_display)

    log.info("SHAP figures saved to {}", FIGURES_DIR)
    return mean_abs


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _build_explainer(model: Any, X_bg: np.ndarray[Any, np.dtype[Any]]) -> Any:
    """Return a SHAP explainer, preferring TreeExplainer."""
    import shap

    # Unwrap CalibratedClassifierCV to reach the underlying tree model
    inner = _unwrap(model)

    try:
        explainer = shap.TreeExplainer(inner, data=X_bg)
        log.debug("Using TreeExplainer (model={})", type(inner).__name__)
        return explainer
    except Exception as exc:
        log.warning("TreeExplainer unavailable ({}); falling back to PermutationExplainer", exc)

    # Fallback: use the (possibly calibrated) model's predict_proba
    predict_fn = getattr(model, "predict_proba", model.predict)
    return shap.PermutationExplainer(predict_fn, X_bg)


def _unwrap(model: Any) -> Any:
    """Unwrap sklearn CalibratedClassifierCV to its base estimator."""
    if hasattr(model, "calibrated_classifiers_"):
        # CalibratedClassifierCV stores a list of fitted sub-estimators
        sub = model.calibrated_classifiers_[0]
        return getattr(sub, "estimator", sub)
    return model


def _to_array(X: pd.DataFrame | np.ndarray[Any, np.dtype[Any]]) -> np.ndarray[Any, np.dtype[Any]]:
    if isinstance(X, pd.DataFrame):
        return X.to_numpy()  # type: ignore[no-any-return]
    return np.asarray(X)


def _save_summary(
    sv: Any,
    X: np.ndarray[Any, np.dtype[Any]],
    feature_names: list[str] | None,
    max_display: int,
) -> None:
    """Beeswarm summary plot (value magnitude + direction per feature)."""
    import matplotlib.pyplot as plt
    import shap

    sv_vals = sv.values if hasattr(sv, "values") else np.asarray(sv)
    shap.summary_plot(
        sv_vals,
        X,
        feature_names=feature_names,
        max_display=max_display,
        show=False,
        plot_type="dot",
    )
    plt.tight_layout()
    out = FIGURES_DIR / "shap_summary.png"
    plt.savefig(out, dpi=120, bbox_inches="tight")
    plt.close("all")
    log.debug("Saved {}", out)


def _save_bar(
    sv: Any,
    feature_names: list[str] | None,
    max_display: int,
) -> dict[str, float]:
    """Horizontal bar chart of mean |SHAP| values; returns full importance dict."""
    import matplotlib.pyplot as plt

    sv_vals = sv.values if hasattr(sv, "values") else np.asarray(sv)
    mean_abs = np.abs(sv_vals).mean(axis=0)

    n = min(max_display, len(mean_abs))
    top_idx = np.argsort(mean_abs)[-n:][::-1]   # descending

    names = (
        [feature_names[i] for i in top_idx]
        if feature_names
        else [f"feature_{i}" for i in top_idx]
    )
    values = [float(mean_abs[i]) for i in top_idx]

    fig, ax = plt.subplots(figsize=(8, max(4, n // 2)))
    ax.barh(names[::-1], values[::-1], color="#1f77b4")
    ax.set_xlabel("Mean |SHAP value|")
    ax.set_title(f"Top {n} Feature Importances (SHAP)")
    plt.tight_layout()

    out = FIGURES_DIR / "shap_bar.png"
    plt.savefig(out, dpi=120, bbox_inches="tight")
    plt.close("all")
    log.debug("Saved {}", out)

    # Return importance for every feature (not just top-N)
    all_names = (
        feature_names
        if feature_names
        else [f"feature_{i}" for i in range(len(mean_abs))]
    )
    return dict(zip(all_names, mean_abs.tolist(), strict=False))

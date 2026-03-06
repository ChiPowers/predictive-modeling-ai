from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd

from service.schemas import Factor

_ARTIFACT_DIR = Path(os.getenv("MODEL_ARTIFACT_DIR", "models/artifacts"))
_MODEL_FILENAME = os.getenv("MODEL_FILENAME", "current.joblib")
_TOP_N_FACTORS = int(os.getenv("TOP_N_FACTORS", "5"))


class ModelLoader:
    """Loads a joblib model artifact and provides scoring with factor explanations."""

    def __init__(self) -> None:
        self._model: Any = None
        self._explainer: Any = None
        self._feature_names: list[str] = []
        self._predictor: Any = None

    def load(self, artifact_dir: Path | None = None, filename: str | None = None) -> None:
        target_name = filename or _MODEL_FILENAME
        path = (artifact_dir or _ARTIFACT_DIR) / target_name
        if not path.exists() and target_name == "current.joblib":
            legacy = (artifact_dir or _ARTIFACT_DIR) / "model.joblib"
            if legacy.exists():
                path = legacy
        if not path.exists():
            raise FileNotFoundError(f"Model artifact not found: {path}")

        self._model = joblib.load(path)
        self._predictor = self._model["pipeline"] if isinstance(self._model, dict) and "pipeline" in self._model else self._model

        # Capture feature names from the model if available
        if isinstance(self._model, dict) and isinstance(self._model.get("feature_cols"), list):
            self._feature_names = list(self._model["feature_cols"])
        elif hasattr(self._predictor, "feature_names_in_"):
            self._feature_names = list(self._predictor.feature_names_in_)
        elif hasattr(self._predictor, "feature_name_"):
            self._feature_names = list(self._predictor.feature_name_)
        else:
            self._feature_names = []

        # Try to load a SHAP explainer saved alongside the model
        explainer_path = path.with_name(path.stem + "_explainer.joblib")
        if explainer_path.exists():
            self._explainer = joblib.load(explainer_path)

    @property
    def is_loaded(self) -> bool:
        return self._model is not None

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _to_frame(self, features: dict[str, Any]) -> pd.DataFrame:
        """Convert a flat feature dict to a single-row DataFrame, aligned to training columns."""
        df = pd.DataFrame([features])
        if self._feature_names:
            # Fill missing columns with NaN; drop extra columns silently
            df = df.reindex(columns=self._feature_names)
        return df

    def _predict_proba(self, df: pd.DataFrame) -> np.ndarray:
        if not hasattr(self._predictor, "predict_proba"):
            raise TypeError("Loaded model does not support predict_proba.")
        proba = self._predictor.predict_proba(df)
        # Return probability of positive class (default = 1)
        return proba[:, 1]

    def _top_factors(self, df: pd.DataFrame, n: int = _TOP_N_FACTORS) -> list[Factor]:
        """Return top-n factors ranked by |SHAP value| or feature importance."""
        feature_names = list(df.columns)

        # Prefer SHAP
        if self._explainer is not None:
            try:
                shap_values = self._explainer(df)
                # shap_values.values shape: (n_rows, n_features) or (n_rows, n_features, n_classes)
                vals = np.array(shap_values.values)
                if vals.ndim == 3:
                    vals = vals[:, :, 1]  # positive-class SHAP
                row_vals = vals[0]
                ranked = sorted(
                    zip(feature_names, row_vals),
                    key=lambda x: abs(x[1]),
                    reverse=True,
                )
                return [Factor(name=name, value=float(v)) for name, v in ranked[:n]]
            except Exception:
                pass  # fall through to feature_importances_

        # Fall back to model feature importances (global, not instance-level)
        if hasattr(self._predictor, "feature_importances_"):
            importances = self._predictor.feature_importances_
            ranked = sorted(
                zip(feature_names, importances),
                key=lambda x: x[1],
                reverse=True,
            )
            return [Factor(name=name, value=float(v)) for name, v in ranked[:n]]

        # No explainability available
        return []

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def score(
        self, features: dict[str, Any], threshold: float = 0.5
    ) -> tuple[float, str, list[Factor]]:
        """Score a single record.

        Returns:
            (pd_score, decision, top_factors)
        """
        if not self.is_loaded:
            raise RuntimeError("Model not loaded. Call load() first.")
        df = self._to_frame(features)
        pd_score = float(self._predict_proba(df)[0])
        decision = "default" if pd_score >= threshold else "current"
        factors = self._top_factors(df)
        return pd_score, decision, factors

    def batch_score(
        self, records: list[tuple[dict[str, Any], float]]
    ) -> list[tuple[float, str, list[Factor]]]:
        """Score multiple records.

        Args:
            records: list of (features_dict, threshold) tuples
        """
        if not self.is_loaded:
            raise RuntimeError("Model not loaded. Call load() first.")

        # Build a combined DataFrame for efficient batch prediction
        dfs = [self._to_frame(feat) for feat, _ in records]
        combined = pd.concat(dfs, ignore_index=True)
        pd_scores = self._predict_proba(combined)

        results: list[tuple[float, str, list[Factor]]] = []
        for i, ((features, threshold), pd_score) in enumerate(zip(records, pd_scores)):
            decision = "default" if pd_score >= threshold else "current"
            row_df = combined.iloc[[i]]
            factors = self._top_factors(row_df)
            results.append((float(pd_score), decision, factors))
        return results


# Module-level singleton — loaded once on startup
model = ModelLoader()

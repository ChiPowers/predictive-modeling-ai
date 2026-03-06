from __future__ import annotations

import joblib
import pandas as pd
from sklearn.linear_model import LogisticRegression

from service.model_loader import ModelLoader


def test_model_loader_supports_wrapped_pipeline_artifact(tmp_path) -> None:
    X = pd.DataFrame({"credit_score": [700, 620, 760, 580], "orig_ltv": [80, 95, 70, 98]})
    y = [0, 1, 0, 1]
    clf = LogisticRegression().fit(X, y)

    artifact = {"pipeline": clf, "feature_cols": ["credit_score", "orig_ltv"]}
    path = tmp_path / "current.joblib"
    joblib.dump(artifact, path)

    loader = ModelLoader()
    loader.load(tmp_path, "current.joblib")
    pd_score, decision, _ = loader.score({"credit_score": 690, "orig_ltv": 85}, threshold=0.5)

    assert 0.0 <= pd_score <= 1.0
    assert decision in {"current", "default"}


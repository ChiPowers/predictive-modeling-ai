from pathlib import Path

import joblib

ARTIFACTS_DIR = Path(__file__).parent / "artifacts"


def save_model(model, name: str) -> Path:
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    path = ARTIFACTS_DIR / f"{name}.joblib"
    joblib.dump(model, path)
    return path


def load_model(name: str):
    path = ARTIFACTS_DIR / f"{name}.joblib"
    return joblib.load(path)

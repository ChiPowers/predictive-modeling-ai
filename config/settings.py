"""Application-wide settings loaded from environment / .env file."""
from __future__ import annotations

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Paths ──────────────────────────────────────────────────────────────
    project_root: Path = Field(default=Path(__file__).resolve().parents[1])
    data_raw_dir: Path = Field(default=Path("data/raw"))
    data_processed_dir: Path = Field(default=Path("data/processed"))
    models_dir: Path = Field(default=Path("models/artifacts"))
    logs_dir: Path = Field(default=Path("logs"))

    # ── Logging ────────────────────────────────────────────────────────────
    log_level: str = Field(default="INFO")
    log_serialize: bool = Field(default=False, description="Emit JSON logs when True")

    # ── Training ───────────────────────────────────────────────────────────
    random_seed: int = Field(default=42)
    test_split: float = Field(default=0.2, ge=0.05, le=0.5)
    forecast_horizon: int = Field(default=30, description="Number of periods to forecast")

    # ── FRED ───────────────────────────────────────────────────────────────
    fred_api_key: str | None = Field(
        default=None,
        description="FRED API key — https://fred.stlouisfed.org/docs/api/api_key.html",
    )

    # ── MLflow ─────────────────────────────────────────────────────────────
    mlflow_tracking_uri: str = Field(default="mlruns", description="MLflow tracking server URI")
    mlflow_experiment_name: str = Field(
        default="predictive-modeling-ai",
        description="Default experiment name for training runs",
    )
    mlflow_registered_model_name: str = Field(
        default="pmai-forecast",
        description="Model Registry name for the trained forecasting model",
    )

    # ── Service ────────────────────────────────────────────────────────────
    api_host: str = Field(default="0.0.0.0")
    api_port: int = Field(default=8000)
    api_reload: bool = Field(default=False)


# Singleton — import and reuse across modules
settings = Settings()

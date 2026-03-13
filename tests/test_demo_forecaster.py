from __future__ import annotations

import pandas as pd

from training.trainer import PROPHET_FORECAST_COLS, DemoTrendForecaster


def test_demo_trend_forecaster_contract() -> None:
    ts = pd.DataFrame({
        "ds": pd.to_datetime(["2024-01-01", "2024-02-01", "2024-03-01"]),
        "y": [0.02, 0.025, 0.03],
    })
    model = DemoTrendForecaster().fit(ts)
    future = model.make_future_dataframe(periods=4, freq="MS")
    pred = model.predict(future)

    assert all(c in pred.columns for c in PROPHET_FORECAST_COLS)
    tail = pred[PROPHET_FORECAST_COLS].tail(4)
    assert len(tail) == 4
    assert tail["yhat"].between(0, 1).all()


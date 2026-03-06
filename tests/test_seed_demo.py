from __future__ import annotations

import pandas as pd

from data_ingestion.seed_demo import seed_demo_data


def test_seed_demo_data_creates_combined_file(tmp_path) -> None:
    out = seed_demo_data(
        output_dir=str(tmp_path),
        filename="demo_2025Q1.csv",
        n_loans=20,
        months=6,
        seed=1,
        overwrite=True,
    )
    path = tmp_path / "demo_2025Q1.csv"
    assert path.exists()
    assert out["rows"] == 120

    df = pd.read_csv(path, sep="|", header=None, dtype=str, encoding="latin-1")
    assert len(df) == 120
    assert df.shape[1] >= 100
    # monthly_reporting_period uses YYYYMM so Prophet training can parse it
    assert df.iloc[0, 2].isdigit()
    assert len(df.iloc[0, 2]) == 6
    assert df.iloc[0, 2].startswith("20")

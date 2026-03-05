"""Generate synthetic Fannie-like combined files for demo environments."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
import random

import pandas as pd


def _add_months(mm_yyyy: str, offset: int) -> str:
    dt = datetime.strptime(mm_yyyy, "%m%Y")
    month_index = (dt.year * 12 + (dt.month - 1)) + offset
    year = month_index // 12
    month = month_index % 12 + 1
    return f"{month:02d}{year:04d}"


def seed_demo_data(
    *,
    output_dir: str = "data/raw/fannie_mae/combined",
    filename: str = "demo_2025Q1.csv",
    n_loans: int = 120,
    months: int = 6,
    seed: int = 42,
    overwrite: bool = True,
) -> dict[str, str | int]:
    """Create a synthetic combined tape that works with the end-to-end demo pipeline."""
    rng = random.Random(seed)
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / filename

    if out_path.exists() and not overwrite:
        return {
            "path": str(out_path),
            "rows": 0,
            "n_loans": n_loans,
            "months": months,
            "note": "file_exists_skipped",
        }

    states = ["CA", "TX", "FL", "CO", "AZ", "GA", "NC", "WA", "VA", "IL"]
    channels = ["R", "B", "C"]
    occupancy = ["P", "I", "S"]
    prop_types = ["SF", "CO", "PU"]
    purposes = ["P", "C", "N", "R"]
    sellers = ["Demo Seller A", "Demo Seller B", "Demo Seller C"]

    rows: list[str] = []
    start_month = "012024"
    for i in range(n_loans):
        loan_id = f"D{2025:04d}{i:08d}"
        orig_upb = rng.randint(120_000, 900_000)
        orig_rate = round(rng.uniform(4.8, 8.5), 3)
        orig_ltv = rng.randint(55, 98)
        orig_cltv = min(105, orig_ltv + rng.randint(0, 6))
        orig_dti = rng.randint(15, 55)
        credit_score = rng.randint(580, 830)
        num_borrowers = 1 if rng.random() < 0.35 else 2
        first_pay = start_month
        maturity = _add_months(first_pay, 360)
        loan_default = rng.random() < 0.03
        default_start = rng.randint(5, max(6, months - 3)) if loan_default else 9999

        for m in range(months):
            vals = [""] * 110
            vals[1] = loan_id
            vals[2] = _add_months(start_month, m)
            vals[3] = rng.choice(channels)
            vals[4] = rng.choice(sellers)
            vals[5] = vals[4]
            vals[7] = f"{orig_rate:.3f}"
            vals[8] = f"{orig_rate + rng.uniform(-0.05, 0.25):.3f}"
            vals[9] = f"{orig_upb:.2f}"
            paydown = int(orig_upb * min(0.45, 0.0065 * m))
            cur_upb = max(orig_upb - paydown, int(orig_upb * 0.55))
            vals[11] = f"{cur_upb:.2f}"
            vals[12] = "360"
            vals[13] = first_pay
            vals[14] = first_pay
            vals[15] = str(m)
            vals[16] = str(max(0, 360 - m))
            vals[17] = str(max(0, 360 - m))
            vals[18] = maturity
            vals[19] = str(orig_ltv)
            vals[20] = str(orig_cltv)
            vals[21] = str(num_borrowers)
            vals[22] = str(orig_dti)
            vals[23] = str(credit_score)
            vals[24] = str(min(850, credit_score + rng.randint(-20, 20)))
            vals[25] = "Y" if rng.random() < 0.35 else "N"
            vals[26] = rng.choice(occupancy)
            vals[27] = rng.choice(prop_types)
            vals[28] = "1"
            vals[29] = rng.choice(purposes)
            vals[30] = rng.choice(states)
            vals[31] = str(rng.randint(10000, 99999))
            vals[32] = str(rng.randint(100, 99999))
            vals[33] = str(rng.choice([0, 0, 0, 12, 18, 25]))
            vals[34] = "ARM" if rng.random() < 0.12 else "FRM"
            vals[35] = "N"
            vals[36] = "N"
            if m >= default_start:
                vals[39] = str(min(6, 1 + (m - default_start)))
            else:
                vals[39] = "0"
            vals[41] = "Y" if (loan_default and m >= default_start + 3 and rng.random() < 0.15) else "N"
            rows.append("|".join(vals))

    out_path.write_text("\n".join(rows) + "\n", encoding="latin-1")

    return {
        "path": str(out_path),
        "rows": len(rows),
        "n_loans": n_loans,
        "months": months,
    }

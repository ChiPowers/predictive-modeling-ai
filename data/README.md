# Data directory

This directory holds raw and processed dataset files.  **All data files are
git-ignored** — only the `.gitkeep` placeholders are tracked.

---

## Fannie Mae Single-Family Loan Performance Data

### Licence / manual download (required)

Fannie Mae requires users to accept a data licence before downloading.
The agent cannot do this on your behalf.

1. Navigate to:
   <https://capitalmarkets.fanniemae.com/credit-risk-transfer/single-family-credit-risk-transfer/fannie-mae-single-family-loan-performance-data>

2. Click **"Access the Data"** and accept the licence agreement.

3. Download the quarters you need.  Each download contains two files:
   | File | Example name | Description |
   |---|---|---|
   | Origination | `Acquisition_2023Q1.txt` | Loan-level origination data |
   | Performance | `Performance_2023Q1.txt` | Monthly performance history |

4. Place the downloaded `.txt` files in:

   ```
   data/raw/fannie_mae/origination/   ← Acquisition_*.txt files
   data/raw/fannie_mae/performance/   ← Performance_*.txt files
   ```

### File format

| Property | Value |
|---|---|
| Delimiter | `\|` (pipe) |
| Encoding | `latin-1` |
| Header row | None (columns assigned by position) |
| Origination columns | 32 (see `data_ingestion/schema.py → ORIGINATION_COLUMNS`) |
| Performance columns | 32 (see `data_ingestion/schema.py → PERFORMANCE_COLUMNS`) |

### Running ingestion

```bash
# Full ingest (all files found in configured directories)
python -m main ingest --source fannie-mae

# Or via Makefile
make ingest SOURCE=fannie-mae
```

To restrict to specific quarters, edit `config/data_paths.yaml`:

```yaml
fannie_mae:
  quarters: ["2022Q1", "2022Q2", "2023Q4"]
```

Or call the Python API directly:

```python
from data_ingestion.ingest_fannie import ingest_origination, ingest_performance

ingest_origination(quarters=["2023Q1"], validate=True, overwrite=False)
ingest_performance(quarters=["2023Q1"], validate=True, overwrite=False)
```

### Outputs

| Path | Description |
|---|---|
| `data/raw/fannie_mae/origination/origination_YYYYQ?_raw.parquet` | Unmodified raw snapshot |
| `data/processed/fannie_mae/origination/origination_YYYYQ?.parquet` | Validated, type-coerced |
| `data/processed/fannie_mae/performance/performance_YYYYQ?.parquet` | Validated, chunked |

### Schema validation

Ingestion runs [pandera](https://pandera.readthedocs.io) checks on every
file.  Validation failures are logged as **warnings** by default so the
pipeline continues with whatever was parsed; set `validate=False` to skip.

The full column specification lives in `data_ingestion/schema.py`.

---

## Adding other datasets

1. Add a loader function in `data_ingestion/sources.py`.
2. Register a new source key in `data_ingestion/loader.py → load()`.
3. Document path conventions here.

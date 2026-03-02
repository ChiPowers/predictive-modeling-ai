# predictive-modeling-ai

This app takes in a public dataset and visualized historic and forecasted trends.

---

## Scoring API

The FastAPI service exposes three endpoints.

### Start the server

```bash
MODEL_ARTIFACT_DIR=models/artifacts MODEL_FILENAME=model.joblib \
  uvicorn service.app:app --host 0.0.0.0 --port 8000 --reload
```

Interactive docs: http://localhost:8000/docs

---

### GET /health

```bash
curl http://localhost:8000/health
```

**Response**

```json
{
  "status": "ok",
  "model_loaded": true,
  "timestamp": 1740000000.0
}
```

---

### POST /score

Score a single loan record.

```bash
curl -s -X POST http://localhost:8000/score \
  -H "Content-Type: application/json" \
  -d '{
    "features": {
      "credit_score": 620,
      "original_ltv": 95.0,
      "original_dti": 45.0,
      "original_interest_rate": 7.25,
      "original_loan_amount": 420000,
      "loan_purpose": "C",
      "property_type": "SF",
      "num_borrowers": 1
    },
    "threshold": 0.5
  }' | python3 -m json.tool
```

**Response**

```json
{
  "pd": 0.312,
  "decision": "current",
  "top_factors": [
    {"name": "original_dti",          "value":  0.18},
    {"name": "original_ltv",          "value":  0.14},
    {"name": "credit_score",          "value": -0.11},
    {"name": "original_interest_rate","value":  0.07},
    {"name": "num_borrowers",         "value": -0.04}
  ]
}
```

`top_factors` values are SHAP values (positive = increases default risk).
`decision` is `"default"` when `pd >= threshold`, otherwise `"current"`.

---

### POST /batch_score

Score multiple records in a single request.

```bash
curl -s -X POST http://localhost:8000/batch_score \
  -H "Content-Type: application/json" \
  -d '{
    "records": [
      {
        "features": {
          "credit_score": 780,
          "original_ltv": 70.0,
          "original_dti": 28.0,
          "original_interest_rate": 5.875,
          "original_loan_amount": 250000,
          "loan_purpose": "P",
          "property_type": "SF",
          "num_borrowers": 2
        },
        "threshold": 0.5
      },
      {
        "features": {
          "credit_score": 580,
          "original_ltv": 97.0,
          "original_dti": 50.0,
          "original_interest_rate": 8.0,
          "original_loan_amount": 510000,
          "loan_purpose": "C",
          "property_type": "CO",
          "num_borrowers": 1
        },
        "threshold": 0.4
      }
    ]
  }' | python3 -m json.tool
```

**Response**

```json
{
  "results": [
    {
      "pd": 0.04,
      "decision": "current",
      "top_factors": [
        {"name": "credit_score",  "value": -0.22},
        {"name": "original_ltv", "value": -0.09}
      ]
    },
    {
      "pd": 0.71,
      "decision": "default",
      "top_factors": [
        {"name": "original_dti",  "value":  0.31},
        {"name": "original_ltv",  "value":  0.25},
        {"name": "credit_score",  "value": -0.18}
      ]
    }
  ],
  "count": 2
}
```

---

### Environment variables

| Variable             | Default              | Description                        |
|----------------------|----------------------|------------------------------------|
| `MODEL_ARTIFACT_DIR` | `models/artifacts`   | Directory containing the artifact  |
| `MODEL_FILENAME`     | `model.joblib`       | Joblib-serialized model file       |
| `TOP_N_FACTORS`      | `5`                  | Number of top factors to return    |

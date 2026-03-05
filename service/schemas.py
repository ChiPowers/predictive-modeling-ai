from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class Factor(BaseModel):
    name: str
    value: float = Field(description="SHAP value (positive = increases default risk)")


class ScoreRequest(BaseModel):
    features: dict[str, Any] = Field(
        description="Loan feature key-value pairs",
        examples=[
            {
                "credit_score": 720,
                "original_ltv": 80.0,
                "original_dti": 35.0,
                "original_interest_rate": 6.5,
                "original_loan_amount": 350000,
                "loan_purpose": "P",
                "property_type": "SF",
                "num_borrowers": 2,
            }
        ],
    )
    threshold: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Decision threshold: pd >= threshold → 'default'",
    )


class ScoreResponse(BaseModel):
    pd: float = Field(ge=0.0, le=1.0, description="Predicted probability of default")
    decision: str = Field(description="'default' or 'current'")
    top_factors: list[Factor] = Field(
        description="Top drivers (by |SHAP value|), descending"
    )


class BatchScoreRequest(BaseModel):
    records: list[ScoreRequest] = Field(min_length=1)


class BatchScoreResponse(BaseModel):
    results: list[ScoreResponse]
    count: int

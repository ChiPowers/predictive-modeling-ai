"""
Decision policy: convert PD scores into approve / review / decline.

Usage::

    from models.policy import Policy, PolicyThresholds, Decision

    thresholds = PolicyThresholds(
        approve_threshold=0.10,
        decline_threshold=0.25,
        review_capacity=0.10,
    )
    policy = Policy(thresholds, name="balanced")

    # Single decision (ignores capacity constraint)
    decision = policy.decide(pd_score=0.07)   # Decision.APPROVE

    # Batch decision (enforces review_capacity if set)
    decisions = policy.decide_batch(pd_scores)
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class Decision(str, Enum):
    APPROVE = "approve"
    REVIEW = "review"
    DECLINE = "decline"


@dataclass
class PolicyThresholds:
    """
    PD thresholds that define the three decision zones.

    Attributes
    ----------
    approve_threshold:
        Applicants with PD < approve_threshold are auto-approved.
    decline_threshold:
        Applicants with PD >= decline_threshold are auto-declined.
    review_capacity:
        Optional. Maximum fraction of the population (0, 1] that can be
        routed to human review. When the raw review band exceeds this
        capacity, only the highest-PD borderline cases are kept in
        review; the remaining lower-risk borderline cases are demoted
        to approve.
    """

    approve_threshold: float
    decline_threshold: float
    review_capacity: Optional[float] = None

    def __post_init__(self) -> None:
        if not (0.0 < self.approve_threshold < self.decline_threshold < 1.0):
            raise ValueError(
                "Must satisfy: 0 < approve_threshold < decline_threshold < 1"
            )
        if self.review_capacity is not None and not (
            0.0 < self.review_capacity <= 1.0
        ):
            raise ValueError("review_capacity must be in (0, 1]")


class Policy:
    """
    Converts PD scores into approve / review / decline decisions.

    Parameters
    ----------
    thresholds:
        PolicyThresholds instance defining the decision boundaries.
    name:
        Human-readable label used in reports.
    """

    def __init__(self, thresholds: PolicyThresholds, name: str = "policy") -> None:
        self.thresholds = thresholds
        self.name = name

    # ------------------------------------------------------------------
    # Core logic
    # ------------------------------------------------------------------

    def decide(self, pd_score: float) -> Decision:
        """
        Single-record decision, ignoring review capacity.

        Lower PD → approve; middle band → review; high PD → decline.
        """
        if pd_score < self.thresholds.approve_threshold:
            return Decision.APPROVE
        if pd_score >= self.thresholds.decline_threshold:
            return Decision.DECLINE
        return Decision.REVIEW

    def decide_batch(self, pd_scores: list[float]) -> list[Decision]:
        """
        Batch decision with optional review-capacity enforcement.

        When ``review_capacity`` is set and the raw borderline segment
        exceeds that fraction of the population, only the top-risk
        borderline applicants (highest PD within the review band) fill
        the available review slots.  The remaining borderline applicants
        — lower risk but above the approve threshold — are demoted to
        **approve** rather than decline, on the assumption that they are
        marginally safe and the queue simply cannot accommodate them.

        Parameters
        ----------
        pd_scores:
            Predicted probability-of-default for each applicant.

        Returns
        -------
        list[Decision]
            One decision per applicant, in the same order as ``pd_scores``.
        """
        decisions: list[Decision] = [self.decide(s) for s in pd_scores]

        cap = self.thresholds.review_capacity
        if cap is None:
            return decisions

        n = len(pd_scores)
        review_indices = [i for i, d in enumerate(decisions) if d == Decision.REVIEW]
        max_review = max(1, int(n * cap))

        if len(review_indices) <= max_review:
            return decisions

        # Keep the highest-PD borderline cases in review; approve the rest.
        review_by_risk = sorted(review_indices, key=lambda i: pd_scores[i], reverse=True)
        demote = set(review_by_risk[max_review:])
        for i in demote:
            decisions[i] = Decision.APPROVE

        return decisions

    # ------------------------------------------------------------------
    # Repr
    # ------------------------------------------------------------------

    def __repr__(self) -> str:
        t = self.thresholds
        cap = f", review_capacity={t.review_capacity}" if t.review_capacity else ""
        return (
            f"Policy(name={self.name!r}, "
            f"approve_threshold={t.approve_threshold}, "
            f"decline_threshold={t.decline_threshold}{cap})"
        )

"""
Offline policy evaluation: compute approval/default/loss metrics and compare
multiple policies, writing JSON and Markdown reports.

Typical usage::

    from models.policy import Policy, PolicyThresholds
    from models.offline_eval import compare_policies

    policies = [
        Policy(PolicyThresholds(0.05, 0.15, review_capacity=0.05), name="strict"),
        Policy(PolicyThresholds(0.10, 0.25, review_capacity=0.10), name="balanced"),
        Policy(PolicyThresholds(0.20, 0.40, review_capacity=0.15), name="lenient"),
    ]

    results = compare_policies(
        policies,
        pd_scores=my_scores,
        actual_defaults=my_labels,  # optional
        lgd=0.60,
        reports_dir="reports",
    )

Run as a script to generate example reports with synthetic data::

    python -m models.offline_eval
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from models.policy import Decision, Policy

# ---------------------------------------------------------------------------
# Metrics container
# ---------------------------------------------------------------------------


@dataclass
class PolicyMetrics:
    """Evaluation metrics for a single policy on a fixed dataset."""

    policy_name: str
    n_total: int
    n_approved: int
    n_review: int
    n_declined: int

    # Rates (fractions of n_total)
    approval_rate: float
    review_rate: float
    decline_rate: float

    # Risk of the approved segment
    mean_pd_approved: float  # mean PD of approved applicants
    expected_loss_rate: float  # sum(PD × LGD, approved) / n_total

    # Only populated when actual default labels are supplied
    actual_default_rate_approved: float | None = None


# ---------------------------------------------------------------------------
# Core evaluation
# ---------------------------------------------------------------------------


def evaluate_policy(
    policy: Policy,
    pd_scores: list[float],
    actual_defaults: list[int] | None = None,
    lgd: float = 1.0,
) -> PolicyMetrics:
    """
    Evaluate *policy* against a scored dataset.

    Parameters
    ----------
    policy:
        A :class:`~models.policy.Policy` instance to evaluate.
    pd_scores:
        Predicted probability-of-default for each applicant (float in [0, 1]).
    actual_defaults:
        Optional ground-truth labels; 1 = defaulted, 0 = did not default.
        Must have the same length as ``pd_scores``.
    lgd:
        Loss-given-default fraction used to compute expected loss (default 1.0).

    Returns
    -------
    PolicyMetrics
    """
    if actual_defaults is not None and len(actual_defaults) != len(pd_scores):
        raise ValueError("pd_scores and actual_defaults must have the same length")

    decisions = policy.decide_batch(pd_scores)
    n = len(decisions)

    approved_pd: list[float] = []
    review_count = 0
    decline_count = 0
    approved_defaults: list[int] = []

    for i, (score, decision) in enumerate(zip(pd_scores, decisions, strict=False)):
        if decision == Decision.APPROVE:
            approved_pd.append(score)
            if actual_defaults is not None:
                approved_defaults.append(actual_defaults[i])
        elif decision == Decision.REVIEW:
            review_count += 1
        else:
            decline_count += 1

    n_approved = len(approved_pd)
    approval_rate = n_approved / n
    review_rate = review_count / n
    decline_rate = decline_count / n

    mean_pd_approved = (sum(approved_pd) / n_approved) if n_approved else 0.0
    expected_loss_rate = (sum(p * lgd for p in approved_pd) / n) if approved_pd else 0.0

    actual_default_rate_approved: float | None = None
    if actual_defaults is not None and approved_defaults:
        actual_default_rate_approved = sum(approved_defaults) / len(approved_defaults)

    return PolicyMetrics(
        policy_name=policy.name,
        n_total=n,
        n_approved=n_approved,
        n_review=review_count,
        n_declined=decline_count,
        approval_rate=approval_rate,
        review_rate=review_rate,
        decline_rate=decline_rate,
        mean_pd_approved=mean_pd_approved,
        expected_loss_rate=expected_loss_rate,
        actual_default_rate_approved=actual_default_rate_approved,
    )


# ---------------------------------------------------------------------------
# Multi-policy comparison + report generation
# ---------------------------------------------------------------------------


def compare_policies(
    policies: list[Policy],
    pd_scores: list[float],
    actual_defaults: list[int] | None = None,
    lgd: float = 1.0,
    reports_dir: str = "reports",
) -> list[PolicyMetrics]:
    """
    Evaluate multiple policies and write JSON + Markdown comparison reports.

    Parameters
    ----------
    policies:
        Ordered list of :class:`~models.policy.Policy` instances.
    pd_scores:
        PD scores for the evaluation dataset.
    actual_defaults:
        Optional ground-truth default labels (same length as ``pd_scores``).
    lgd:
        Loss-given-default fraction (default 1.0).
    reports_dir:
        Directory where ``policy_comparison.json`` and
        ``policy_comparison.md`` will be written (created if absent).

    Returns
    -------
    list[PolicyMetrics]
        One :class:`PolicyMetrics` per policy, in input order.
    """
    results = [evaluate_policy(policy, pd_scores, actual_defaults, lgd) for policy in policies]

    dataset_info = {
        "n": len(pd_scores),
        "mean_pd": round(sum(pd_scores) / len(pd_scores), 6),
        "lgd": lgd,
        "has_actual_labels": actual_defaults is not None,
    }

    out = Path(reports_dir)
    out.mkdir(parents=True, exist_ok=True)

    _write_json(results, dataset_info, out / "policy_comparison.json")
    _write_markdown(results, dataset_info, out / "policy_comparison.md")

    return results


# ---------------------------------------------------------------------------
# Report writers
# ---------------------------------------------------------------------------


def _write_json(
    results: list[PolicyMetrics],
    dataset_info: dict[str, Any],
    path: Path,
) -> None:
    payload = {
        "dataset": dataset_info,
        "policies": [asdict(r) for r in results],
        "summary": _build_summary(results),
    }
    path.write_text(json.dumps(payload, indent=2))


def _build_summary(results: list[PolicyMetrics]) -> dict[str, Any]:
    """Identify the best policy on key dimensions."""
    best_approval = max(results, key=lambda r: r.approval_rate)
    best_loss = min(results, key=lambda r: r.expected_loss_rate)
    return {
        "highest_approval_rate": {
            "policy": best_approval.policy_name,
            "value": round(best_approval.approval_rate, 4),
        },
        "lowest_expected_loss_rate": {
            "policy": best_loss.policy_name,
            "value": round(best_loss.expected_loss_rate, 6),
        },
    }


def _write_markdown(
    results: list[PolicyMetrics],
    dataset_info: dict[str, Any],
    path: Path,
) -> None:
    has_actuals = dataset_info["has_actual_labels"]
    lines: list[str] = [
        "# Policy Comparison Report",
        "",
        "## Dataset",
        f"- **Records**: {dataset_info['n']:,}",
        f"- **Mean PD**: {dataset_info['mean_pd']:.4f}",
        f"- **LGD**: {dataset_info['lgd']:.2f}",
        f"- **Actual default labels**: {'yes' if has_actuals else 'no'}",
        "",
        "## Decision Rate Breakdown",
        "",
    ]

    # Table 1 — volume breakdown
    lines += [
        "| Policy | Approve | Review | Decline |",
        "|--------|--------:|-------:|--------:|",
    ]
    for r in results:
        lines.append(
            f"| {r.policy_name} "
            f"| {r.approval_rate:.1%} "
            f"| {r.review_rate:.1%} "
            f"| {r.decline_rate:.1%} |"
        )

    lines += [
        "",
        "## Risk & Loss Metrics",
        "",
    ]

    # Table 2 — risk metrics
    header = "| Policy | Mean PD (approved) | Expected Loss Rate"
    sep = "|--------|-------------------:|-------------------:"
    if has_actuals:
        header += " | Actual Default Rate (approved)"
        sep += "|------------------------------:"
    header += " |"
    sep += "|"
    lines += [header, sep]

    for r in results:
        row = f"| {r.policy_name} " f"| {r.mean_pd_approved:.4f} " f"| {r.expected_loss_rate:.4f}"
        if has_actuals:
            adr = (
                f"{r.actual_default_rate_approved:.2%}"
                if r.actual_default_rate_approved is not None
                else "N/A"
            )
            row += f" | {adr}"
        row += " |"
        lines.append(row)

    summary = _build_summary(results)
    lines += [
        "",
        "## Summary",
        "",
        f"- **Highest approval rate**: `{summary['highest_approval_rate']['policy']}` "
        f"({summary['highest_approval_rate']['value']:.1%})",
        f"- **Lowest expected loss rate**: `{summary['lowest_expected_loss_rate']['policy']}` "
        f"({summary['lowest_expected_loss_rate']['value']:.4f})",
        "",
        "## Metric Definitions",
        "",
        "| Metric | Definition |",
        "|--------|-----------|",
        "| Approval % | Fraction of applicants auto-approved |",
        "| Review % | Fraction routed to human review |",
        "| Decline % | Fraction auto-declined |",
        "| Mean PD (approved) | Average predicted default probability among approved applicants |",
        "| Expected Loss Rate | `sum(PD × LGD, approved) / n_total` — portfolio-level loss exposure |",
        "| Actual Default Rate | Observed default rate among approved applicants (requires labels) |",
        "",
        "_Generated by `models/offline_eval.py`_",
    ]

    path.write_text("\n".join(lines) + "\n")


# ---------------------------------------------------------------------------
# CLI entry point — generates example reports with synthetic data
# ---------------------------------------------------------------------------


def _make_synthetic_dataset(n: int = 5000, seed: int = 42) -> tuple[list[float], list[int]]:
    """
    Synthetic credit-risk dataset.

    PD scores drawn from Beta(1.2, 9) — right-skewed, mean ~0.12,
    resembling a typical consumer lending portfolio.
    Actual defaults sampled by treating PD as the Bernoulli parameter.
    """
    import random

    random.seed(seed)

    # Beta(a, b) via gamma variates
    a, b = 1.2, 9.0
    pd_scores: list[float] = []
    for _ in range(n):
        x = _beta_variate(a, b, random)
        # Clamp to a sensible range
        pd_scores.append(min(max(x, 0.001), 0.999))

    actual_defaults: list[int] = [1 if random.random() < p else 0 for p in pd_scores]
    return pd_scores, actual_defaults


def _beta_variate(alpha: float, beta: float, rng: Any) -> float:
    """Sample from Beta(alpha, beta) using the stdlib random module."""
    # random.betavariate available since Python 3.x
    return float(rng.betavariate(alpha, beta))


if __name__ == "__main__":
    import sys

    from models.policy import Policy, PolicyThresholds

    reports_dir = sys.argv[1] if len(sys.argv) > 1 else "reports"

    print("Generating synthetic dataset (n=5000)…")
    pd_scores, actual_defaults = _make_synthetic_dataset(n=5000, seed=42)

    policies = [
        Policy(
            PolicyThresholds(approve_threshold=0.05, decline_threshold=0.15, review_capacity=0.05),
            name="strict",
        ),
        Policy(
            PolicyThresholds(approve_threshold=0.10, decline_threshold=0.25, review_capacity=0.10),
            name="balanced",
        ),
        Policy(
            PolicyThresholds(approve_threshold=0.20, decline_threshold=0.40, review_capacity=0.15),
            name="lenient",
        ),
    ]

    print(f"Evaluating {len(policies)} policies…")
    results = compare_policies(
        policies,
        pd_scores=pd_scores,
        actual_defaults=actual_defaults,
        lgd=0.60,
        reports_dir=reports_dir,
    )

    print(f"\nReports written to {reports_dir}/")
    print(f"  {reports_dir}/policy_comparison.json")
    print(f"  {reports_dir}/policy_comparison.md\n")

    # Print summary table to stdout
    print(
        f"{'Policy':<12} {'Approve':>8} {'Review':>8} {'Decline':>8} {'Mean PD':>10} {'Exp Loss':>10}"
    )
    print("-" * 60)
    for r in results:
        print(
            f"{r.policy_name:<12} "
            f"{r.approval_rate:>7.1%} "
            f"{r.review_rate:>7.1%} "
            f"{r.decline_rate:>7.1%} "
            f"{r.mean_pd_approved:>10.4f} "
            f"{r.expected_loss_rate:>10.4f}"
        )

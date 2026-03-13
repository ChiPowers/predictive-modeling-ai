"""Tests for training.trainer."""

from __future__ import annotations

import pytest


def test_train_model_unknown_raises_value_error() -> None:
    """train_model raises ValueError for an unsupported model key."""
    from training.trainer import train_model

    with pytest.raises(ValueError, match="Unknown model"):
        train_model("not-a-real-model")

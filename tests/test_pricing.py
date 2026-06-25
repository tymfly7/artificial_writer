"""Tests for the model pricing helper."""

from __future__ import annotations

import pytest

from artificial_writer.core.summarizers import pricing


@pytest.mark.parametrize(
    "model",
    ["claude-haiku-4-5-20251001", "claude-haiku-4-5", "gpt-4o-mini"],
)
def test_cost_for_known_model_is_positive(model: str) -> None:
    cost = pricing.cost_for(model, input_tokens=1000, output_tokens=1000)
    assert cost is not None
    assert cost > 0


def test_cost_for_unknown_model_is_none() -> None:
    assert pricing.cost_for("totally-made-up-model", 1000, 1000) is None


def test_cost_for_uses_per_1k_rates() -> None:
    # gpt-4o-mini: $0.00015/1k input, $0.0006/1k output.
    cost = pricing.cost_for("gpt-4o-mini", input_tokens=2000, output_tokens=1000)
    assert cost == pytest.approx(2 * 0.00015 + 1 * 0.0006)

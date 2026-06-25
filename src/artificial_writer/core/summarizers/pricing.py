"""Per-model token pricing and a cost helper.

Prices are USD per 1,000 tokens, as ``(input, output)`` tuples. Only the models
this app can actually select need entries; an unknown model yields ``None`` (we
do not pretend a cost we cannot compute is zero).

Sources (per 1M tokens, divided by 1000 here):
- Claude Haiku 4.5: $1.00 input / $5.00 output (Anthropic, via the claude-api skill).
- OpenAI gpt-4o-mini: $0.15 input / $0.60 output.
"""

from __future__ import annotations

# model id -> (input_usd_per_1k, output_usd_per_1k)
_PRICING: dict[str, tuple[float, float]] = {
    # Claude (Anthropic). Both the dated id used in config.py and the alias.
    "claude-haiku-4-5-20251001": (0.001, 0.005),
    "claude-haiku-4-5": (0.001, 0.005),
    # OpenAI.
    "gpt-4o-mini": (0.00015, 0.0006),
}


def cost_for(model: str, input_tokens: int, output_tokens: int) -> float | None:
    """Return the USD cost for a call, or ``None`` if the model is unknown."""
    rates = _PRICING.get(model)
    if rates is None:
        return None
    input_rate, output_rate = rates
    return (input_tokens / 1000) * input_rate + (output_tokens / 1000) * output_rate

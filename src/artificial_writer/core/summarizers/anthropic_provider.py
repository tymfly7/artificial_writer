"""Anthropic (Claude) summarizer (optional, requires an API key and the SDK)."""

from __future__ import annotations

import time

from ..errors import ConfigurationError, SummarizationError
from ..output_format import OutputFormat
from . import pricing
from .base import Summarizer, SummaryResult
from .prompt import build_prompt


class AnthropicSummarizer(Summarizer):
    """Summarize text using Anthropic's Messages API."""

    name = "anthropic"

    def __init__(
        self, api_key: str | None, model: str = "claude-haiku-4-5-20251001"
    ) -> None:
        if not api_key:
            raise ConfigurationError(
                "Anthropic summarizer requires AW_ANTHROPIC_API_KEY to be set."
            )
        try:
            import anthropic
        except ImportError as exc:  # pragma: no cover - import guard
            raise ConfigurationError(
                "The 'anthropic' package is not installed. Install it with "
                "`pip install artificial-writer[anthropic]`."
            ) from exc

        self._client = anthropic.Anthropic(api_key=api_key)
        self._model = model

    def summarize(
        self, text: str, *, output_format: OutputFormat = OutputFormat.PROSE
    ) -> SummaryResult:
        start = time.perf_counter()
        try:
            message = self._client.messages.create(
                model=self._model,
                max_tokens=1024,
                messages=[{"role": "user", "content": build_prompt(text, output_format)}],
            )
            summary = "".join(
                block.text for block in message.content if block.type == "text"
            ).strip()
        except Exception as exc:  # noqa: BLE001 - surface any SDK error uniformly
            raise SummarizationError(f"Anthropic request failed: {exc}") from exc

        if not summary:
            raise SummarizationError("Anthropic returned an empty summary.")

        usage = getattr(message, "usage", None)
        input_tokens = getattr(usage, "input_tokens", None)
        output_tokens = getattr(usage, "output_tokens", None)
        cost_usd = (
            pricing.cost_for(self._model, input_tokens, output_tokens)
            if input_tokens is not None and output_tokens is not None
            else None
        )

        return SummaryResult(
            summary=summary,
            backend=self.name,
            model=self._model,
            elapsed_seconds=time.perf_counter() - start,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=cost_usd,
        )

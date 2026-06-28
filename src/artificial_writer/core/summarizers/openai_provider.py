"""OpenAI-backed summarizer (optional, requires an API key and the openai SDK)."""

from __future__ import annotations

import time

from ..errors import ConfigurationError, SummarizationError
from ..output_format import OutputFormat
from . import pricing
from .base import Summarizer, SummaryResult
from .prompt import build_prompt


class OpenAISummarizer(Summarizer):
    """Summarize text using OpenAI's chat completions API."""

    name = "openai"
    #: Default input cap (tokens); factory overrides it from AW_OPENAI_MAX_INPUT_TOKENS.
    DEFAULT_MAX_INPUT_TOKENS = 12_000

    def __init__(
        self,
        api_key: str | None,
        model: str = "gpt-4o-mini",
        max_input_tokens: int | None = DEFAULT_MAX_INPUT_TOKENS,
    ) -> None:
        if not api_key:
            raise ConfigurationError(
                "OpenAI summarizer requires AW_OPENAI_API_KEY to be set."
            )
        try:
            from openai import OpenAI
        except ImportError as exc:  # pragma: no cover - import guard
            raise ConfigurationError(
                "The 'openai' package is not installed. Install it with "
                "`pip install artificial-writer[openai]`."
            ) from exc

        self._client = OpenAI(api_key=api_key)
        self._model = model
        self.max_input_tokens = max_input_tokens

    def summarize(
        self, text: str, *, output_format: OutputFormat = OutputFormat.PROSE
    ) -> SummaryResult:
        text = self._prepare(text)
        start = time.perf_counter()
        try:
            response = self._client.chat.completions.create(
                model=self._model,
                messages=[{"role": "user", "content": build_prompt(text, output_format)}],
            )
            summary = (response.choices[0].message.content or "").strip()
        except Exception as exc:  # noqa: BLE001 - surface any SDK error uniformly
            raise SummarizationError(f"OpenAI request failed: {exc}") from exc

        if not summary:
            raise SummarizationError("OpenAI returned an empty summary.")

        usage = getattr(response, "usage", None)
        input_tokens = getattr(usage, "prompt_tokens", None)
        output_tokens = getattr(usage, "completion_tokens", None)
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

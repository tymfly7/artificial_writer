"""OpenAI-backed summarizer (optional, requires an API key and the openai SDK)."""

from __future__ import annotations

import time

from ..errors import ConfigurationError, SummarizationError
from .base import Summarizer, SummaryResult
from .prompt import build_prompt


class OpenAISummarizer(Summarizer):
    """Summarize text using OpenAI's chat completions API."""

    name = "openai"

    def __init__(self, api_key: str | None, model: str = "gpt-4o-mini") -> None:
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

    def summarize(self, text: str) -> SummaryResult:
        start = time.perf_counter()
        try:
            response = self._client.chat.completions.create(
                model=self._model,
                messages=[{"role": "user", "content": build_prompt(text)}],
            )
            summary = (response.choices[0].message.content or "").strip()
        except Exception as exc:  # noqa: BLE001 - surface any SDK error uniformly
            raise SummarizationError(f"OpenAI request failed: {exc}") from exc

        if not summary:
            raise SummarizationError("OpenAI returned an empty summary.")

        return SummaryResult(
            summary=summary,
            backend=self.name,
            model=self._model,
            elapsed_seconds=time.perf_counter() - start,
        )

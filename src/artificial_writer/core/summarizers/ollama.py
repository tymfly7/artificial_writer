"""Free local-LLM summarizer backed by Ollama (https://ollama.com).

Ollama exposes an HTTP API on localhost, so this backend needs no API key and
no extra Python dependencies -- just a running ``ollama serve`` and a pulled
model (e.g. ``ollama pull llama3.2``).
"""

from __future__ import annotations

import logging
import time

import requests

from ..errors import SummarizationError
from ..output_format import OutputFormat
from .base import Summarizer, SummaryResult
from .prompt import build_prompt

logger = logging.getLogger(__name__)


class OllamaSummarizer(Summarizer):
    """Summarize text using a locally running Ollama model."""

    name = "ollama"

    def __init__(
        self,
        model: str = "llama3.2",
        host: str = "http://localhost:11434",
        timeout: float = 120.0,
    ) -> None:
        self._model = model
        self._host = host.rstrip("/")
        self._timeout = timeout

    def summarize(
        self, text: str, *, output_format: OutputFormat = OutputFormat.PROSE
    ) -> SummaryResult:
        start = time.perf_counter()
        try:
            response = requests.post(
                f"{self._host}/api/generate",
                json={
                    "model": self._model,
                    "prompt": build_prompt(text, output_format),
                    "stream": False,
                },
                timeout=self._timeout,
            )
            response.raise_for_status()
            payload = response.json()
        except requests.exceptions.RequestException as exc:
            raise SummarizationError(
                f"Could not reach Ollama at {self._host}. Is `ollama serve` running "
                f"and `{self._model}` pulled? ({exc})"
            ) from exc

        summary = (payload.get("response") or "").strip()
        if not summary:
            raise SummarizationError("Ollama returned an empty summary.")

        return SummaryResult(
            summary=summary,
            backend=self.name,
            model=self._model,
            elapsed_seconds=time.perf_counter() - start,
            cost_usd=0.0,
        )

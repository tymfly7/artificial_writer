"""Pluggable summarizer backends.

The default :class:`ExtractiveSummarizer` is free and works offline. Optional
LLM backends (Ollama, OpenAI, Anthropic) are imported lazily by the factory so
their dependencies are only needed when actually selected.
"""

from __future__ import annotations

from .base import (
    Summarizer,
    SummaryResult,
    estimate_tokens,
    trim_to_sentence,
    trim_to_tokens,
)
from .extractive import ExtractiveSummarizer
from .factory import build_summarizer
from .ollama import list_models as list_ollama_models

__all__ = [
    "Summarizer",
    "SummaryResult",
    "estimate_tokens",
    "trim_to_sentence",
    "trim_to_tokens",
    "ExtractiveSummarizer",
    "build_summarizer",
    "list_ollama_models",
]

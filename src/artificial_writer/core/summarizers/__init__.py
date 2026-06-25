"""Pluggable summarizer backends.

The default :class:`ExtractiveSummarizer` is free and works offline. Optional
LLM backends (Ollama, OpenAI, Anthropic) are imported lazily by the factory so
their dependencies are only needed when actually selected.
"""

from __future__ import annotations

from .base import Summarizer, SummaryResult
from .extractive import ExtractiveSummarizer
from .factory import build_summarizer

__all__ = ["Summarizer", "SummaryResult", "ExtractiveSummarizer", "build_summarizer"]

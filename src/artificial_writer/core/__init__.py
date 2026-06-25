"""Shared core of Artificial Writer: the engine every front-end is built on.

The CLI, desktop GUI, and web app are all thin wrappers around this package.
It owns the whole pipeline -- fetching, summarizing, and storage -- plus the
typed configuration and domain errors. Front-ends should depend on ``core`` and
never on each other.

    URL --(fetcher)--> clean text --(summarizer)--> summary --(storage)--> disk
"""

from __future__ import annotations

from .config import Settings, SummarizerType, configure_logging, get_settings
from .errors import (
    ArtificialWriterError,
    ConfigurationError,
    FetchError,
    SummarizationError,
)
from .fetcher import FetchedArticle, TextFetcher
from .pipeline import Pipeline, PipelineResult
from .storage import Storage
from .summarizers import Summarizer, SummaryResult, build_summarizer

__all__ = [
    "Settings",
    "SummarizerType",
    "configure_logging",
    "get_settings",
    "ArtificialWriterError",
    "ConfigurationError",
    "FetchError",
    "SummarizationError",
    "FetchedArticle",
    "TextFetcher",
    "Pipeline",
    "PipelineResult",
    "Storage",
    "Summarizer",
    "SummaryResult",
    "build_summarizer",
]

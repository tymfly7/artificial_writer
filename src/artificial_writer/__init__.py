"""Artificial Writer: fetch an article from a URL and summarize it.

The package is built around a small, well-defined pipeline:

    URL --(fetcher)--> clean text --(summarizer)--> summary --(storage)--> disk

Summarizers are pluggable (see :mod:`artificial_writer.summarizers`) and the
default works fully offline and free.
"""

from __future__ import annotations

__version__ = "1.0.0"

from .pipeline import Pipeline, PipelineResult

__all__ = ["Pipeline", "PipelineResult", "__version__"]

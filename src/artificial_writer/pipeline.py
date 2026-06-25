"""Orchestrate the fetch -> summarize -> (optionally) store workflow.

This is the single entry point shared by every front-end (CLI, GUI, web), which
keeps behavior consistent and the interfaces thin.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

from .config import Settings, get_settings
from .fetcher import FetchedArticle, TextFetcher
from .storage import Storage
from .summarizers import Summarizer, SummaryResult, build_summarizer

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PipelineResult:
    """Everything produced by a single run of the pipeline."""

    article: FetchedArticle
    summary: SummaryResult
    saved_path: Path | None = None


class Pipeline:
    """Wire together a fetcher, a summarizer, and storage."""

    def __init__(
        self,
        settings: Settings | None = None,
        *,
        fetcher: TextFetcher | None = None,
        summarizer: Summarizer | None = None,
        storage: Storage | None = None,
    ) -> None:
        self._settings = settings or get_settings()
        self._fetcher = fetcher or TextFetcher(timeout=self._settings.request_timeout)
        self._summarizer = summarizer or build_summarizer(self._settings)
        self._storage = storage or Storage()

    @property
    def summarizer(self) -> Summarizer:
        return self._summarizer

    def fetch(self, url: str) -> FetchedArticle:
        """Fetch and clean ``url`` without summarizing (step one of two)."""
        article = self._fetcher.fetch(url)
        logger.info("Fetched %d words from %s", article.word_count, url)
        return article

    def summarize_text(
        self, text: str, *, title: str = "Untitled", save: bool = False
    ) -> PipelineResult:
        """Summarize raw ``text`` that has already been obtained elsewhere."""
        trimmed = text.strip()[: self._settings.max_input_chars]
        summary = self._summarizer.summarize(trimmed)
        article = FetchedArticle(url="", title=title, text=trimmed)
        saved_path = (
            self._storage.save_summary(title, trimmed, summary.summary) if save else None
        )
        return PipelineResult(article=article, summary=summary, saved_path=saved_path)

    def run(self, url: str, *, save: bool = False) -> PipelineResult:
        """Fetch ``url``, summarize it, and optionally persist the result."""
        article = self._fetcher.fetch(url)
        logger.info("Fetched %d words from %s", article.word_count, url)

        text = article.text[: self._settings.max_input_chars]
        summary = self._summarizer.summarize(text)
        logger.info(
            "Summarized via %s in %.2fs", summary.backend, summary.elapsed_seconds
        )

        saved_path = None
        if save:
            saved_path = self._storage.save_summary(article.title, article.text, summary.summary)

        return PipelineResult(article=article, summary=summary, saved_path=saved_path)

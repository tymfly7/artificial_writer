"""Tests for the pipeline orchestration using fakes."""

from __future__ import annotations

from pathlib import Path

from artificial_writer.core.config import Settings, SummarizerType
from artificial_writer.core.fetcher import FetchedArticle
from artificial_writer.core.pipeline import Pipeline
from artificial_writer.core.storage import Storage
from artificial_writer.core.summarizers.base import Summarizer, SummaryResult

from .conftest import SAMPLE_TEXT


class FakeFetcher:
    def fetch(self, url: str) -> FetchedArticle:
        return FetchedArticle(url=url, title="Fake Title", text=SAMPLE_TEXT)


class FakeSummarizer(Summarizer):
    name = "fake"

    def summarize(self, text: str) -> SummaryResult:
        return SummaryResult(summary="FAKE SUMMARY", backend=self.name, elapsed_seconds=0.01)


def _settings() -> Settings:
    return Settings(summarizer=SummarizerType.EXTRACTIVE, max_input_chars=5000)


def test_run_returns_summary_without_saving() -> None:
    pipeline = Pipeline(_settings(), fetcher=FakeFetcher(), summarizer=FakeSummarizer())
    result = pipeline.run("https://example.com/x")

    assert result.summary.summary == "FAKE SUMMARY"
    assert result.article.title == "Fake Title"
    assert result.saved_path is None


def test_run_saves_when_requested(tmp_path: Path) -> None:
    pipeline = Pipeline(
        _settings(),
        fetcher=FakeFetcher(),
        summarizer=FakeSummarizer(),
        storage=Storage(base_dir=tmp_path),
    )
    result = pipeline.run("https://example.com/x", save=True)

    assert result.saved_path is not None
    assert result.saved_path.exists()


def test_input_is_truncated_to_max_chars() -> None:
    captured: dict[str, str] = {}

    class CapturingSummarizer(FakeSummarizer):
        def summarize(self, text: str) -> SummaryResult:
            captured["text"] = text
            return super().summarize(text)

    settings = Settings(max_input_chars=100)
    pipeline = Pipeline(settings, fetcher=FakeFetcher(), summarizer=CapturingSummarizer())
    pipeline.run("https://example.com/x")

    assert len(captured["text"]) == 100


def test_summarize_text_uses_real_extractive_default() -> None:
    pipeline = Pipeline(_settings(), fetcher=FakeFetcher())
    result = pipeline.summarize_text(SAMPLE_TEXT, title="Direct")

    assert result.summary.backend == "extractive"
    assert result.article.title == "Direct"

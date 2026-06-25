"""Tests for the offline extractive summarizer."""

from __future__ import annotations

import pytest

from artificial_writer.summarizers.extractive import ExtractiveSummarizer

from .conftest import SAMPLE_TEXT


def test_returns_requested_number_of_sentences() -> None:
    result = ExtractiveSummarizer(num_sentences=2).summarize(SAMPLE_TEXT)

    assert result.backend == "extractive"
    # Two sentences -> roughly two terminal punctuation marks.
    assert result.summary.count(".") <= 3
    assert len(result.summary) < len(SAMPLE_TEXT)


def test_short_text_returned_whole() -> None:
    text = "Only one sentence here."
    result = ExtractiveSummarizer(num_sentences=5).summarize(text)
    assert "Only one sentence" in result.summary


def test_summary_sentences_preserve_source_order() -> None:
    result = ExtractiveSummarizer(num_sentences=3).summarize(SAMPLE_TEXT)
    chosen = [s.strip() for s in result.summary.split(".") if s.strip()]
    positions = [SAMPLE_TEXT.find(s) for s in chosen]
    assert positions == sorted(positions)


def test_empty_text() -> None:
    result = ExtractiveSummarizer().summarize("")
    assert result.summary == ""


def test_invalid_sentence_count_rejected() -> None:
    with pytest.raises(ValueError):
        ExtractiveSummarizer(num_sentences=0)

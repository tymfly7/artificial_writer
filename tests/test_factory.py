"""Tests for the summarizer factory's backend selection."""

from __future__ import annotations

import pytest

from artificial_writer.config import Settings, SummarizerType
from artificial_writer.errors import ConfigurationError
from artificial_writer.summarizers import build_summarizer
from artificial_writer.summarizers.extractive import ExtractiveSummarizer


def test_factory_builds_extractive_by_default() -> None:
    summarizer = build_summarizer(Settings(summarizer=SummarizerType.EXTRACTIVE))
    assert isinstance(summarizer, ExtractiveSummarizer)


def test_factory_accepts_raw_string_summarizer() -> None:
    # The GUI selects a backend via ``model_copy``, which does NOT re-validate,
    # so ``summarizer`` can reach the factory as a plain (possibly mixed-case)
    # string. The factory must coerce it rather than failing.
    settings = Settings().model_copy(update={"summarizer": "Extractive"})
    assert isinstance(build_summarizer(settings), ExtractiveSummarizer)


def test_factory_rejects_unknown_summarizer() -> None:
    settings = Settings().model_copy(update={"summarizer": "nope"})
    with pytest.raises(ConfigurationError, match="Unknown summarizer"):
        build_summarizer(settings)

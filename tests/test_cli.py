"""Tests for the command-line interface."""

from __future__ import annotations

import json

import pytest

from artificial_writer.cli import app as cli
from artificial_writer.core.errors import FetchError
from artificial_writer.core.fetcher import FetchedArticle
from artificial_writer.core.pipeline import PipelineResult
from artificial_writer.core.summarizers.base import SummaryResult


def _fake_result() -> PipelineResult:
    return PipelineResult(
        article=FetchedArticle(url="https://x.test", title="Title", text="body text"),
        summary=SummaryResult(summary="a summary", backend="extractive", elapsed_seconds=0.02),
    )


def test_cli_text_output(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture) -> None:
    monkeypatch.setattr(cli.Pipeline, "run", lambda self, url, save=False: _fake_result())

    exit_code = cli.main(["https://x.test"])

    out = capsys.readouterr().out
    assert exit_code == 0
    assert "a summary" in out
    assert "Title" in out


def test_cli_json_output(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture) -> None:
    monkeypatch.setattr(cli.Pipeline, "run", lambda self, url, save=False: _fake_result())

    exit_code = cli.main(["https://x.test", "--json"])

    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert payload["summary"] == "a summary"
    assert payload["backend"] == "extractive"


def test_cli_handles_errors(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture) -> None:
    def boom(self: object, url: str, save: bool = False) -> PipelineResult:
        raise FetchError("could not fetch")

    monkeypatch.setattr(cli.Pipeline, "run", boom)

    exit_code = cli.main(["https://x.test"])

    assert exit_code == 1
    assert "could not fetch" in capsys.readouterr().err

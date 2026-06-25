"""Tests for the fetcher registry's URL-based dispatch."""

from __future__ import annotations

import pytest

from artificial_writer.core.errors import FetchError
from artificial_writer.core.fetchers import registry
from artificial_writer.core.fetchers.base import FetchedArticle


def _sentinel(name: str) -> object:
    article = FetchedArticle(url=name, title=name, text=name)

    def fetch(self: object, source: str) -> FetchedArticle:
        return article

    return fetch


@pytest.mark.parametrize(
    ("url", "target"),
    [
        ("https://example.com/article", "artificial_writer.core.fetchers.html.HtmlFetcher.fetch"),
        ("https://example.com/paper.pdf", "artificial_writer.core.fetchers.pdf.PdfFetcher.fetch"),
        (
            "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            "artificial_writer.core.fetchers.youtube.YouTubeFetcher.fetch",
        ),
        (
            "https://youtu.be/dQw4w9WgXcQ",
            "artificial_writer.core.fetchers.youtube.YouTubeFetcher.fetch",
        ),
    ],
)
def test_registry_dispatches_by_url(
    monkeypatch: pytest.MonkeyPatch, url: str, target: str
) -> None:
    monkeypatch.setattr(target, _sentinel(target))
    article = registry.fetch(url)
    assert article.title == target


@pytest.mark.parametrize("bad_url", ["", "not-a-url", "ftp://example.com", "example.com"])
def test_registry_rejects_non_http(bad_url: str) -> None:
    with pytest.raises(FetchError):
        registry.fetch(bad_url)

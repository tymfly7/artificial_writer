"""Tests for the URL fetcher (network is mocked with the ``responses`` library)."""

from __future__ import annotations

import pytest
import responses

from artificial_writer.errors import FetchError
from artificial_writer.fetcher import TextFetcher

from .conftest import SAMPLE_HTML


@responses.activate
def test_fetch_extracts_title_and_paragraphs() -> None:
    url = "https://example.com/solar"
    responses.add(responses.GET, url, body=SAMPLE_HTML, content_type="text/html")

    article = TextFetcher().fetch(url)

    assert article.title == "The Future of Solar Power"
    assert "Solar power is growing" in article.text
    # Boilerplate must be stripped.
    assert "ignore me" not in article.text
    assert "copyright" not in article.text
    assert article.word_count > 10


@pytest.mark.parametrize("bad_url", ["", "not-a-url", "ftp://example.com", "example.com"])
def test_invalid_urls_rejected(bad_url: str) -> None:
    with pytest.raises(FetchError):
        TextFetcher().fetch(bad_url)


@responses.activate
def test_http_error_raises_fetch_error() -> None:
    url = "https://example.com/missing"
    responses.add(responses.GET, url, status=404)

    with pytest.raises(FetchError):
        TextFetcher().fetch(url)


@responses.activate
def test_empty_page_raises() -> None:
    url = "https://example.com/empty"
    responses.add(responses.GET, url, body="<html><body></body></html>")

    with pytest.raises(FetchError):
        TextFetcher().fetch(url)

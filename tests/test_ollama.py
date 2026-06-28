"""Tests for the Ollama backend's model discovery (network mocked with ``responses``)."""

from __future__ import annotations

import responses

from artificial_writer.core.summarizers.ollama import list_models

_TAGS_URL = "http://localhost:11434/api/tags"


@responses.activate
def test_list_models_returns_sorted_names() -> None:
    responses.add(
        responses.GET,
        _TAGS_URL,
        json={"models": [{"name": "llama3.2"}, {"name": "gemma3"}, {"name": "phi4"}]},
    )

    assert list_models() == ["gemma3", "llama3.2", "phi4"]


@responses.activate
def test_list_models_skips_malformed_entries() -> None:
    responses.add(
        responses.GET,
        _TAGS_URL,
        json={"models": [{"name": "llama3.2"}, {}, {"size": 1}, "junk"]},
    )

    assert list_models() == ["llama3.2"]


@responses.activate
def test_list_models_returns_empty_when_unreachable() -> None:
    # Ollama not running -> connection error -> graceful empty list, no raise.
    responses.add(responses.GET, _TAGS_URL, status=500)

    assert list_models() == []

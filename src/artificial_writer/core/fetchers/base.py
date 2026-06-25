"""Shared types for the fetcher registry."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class FetchedArticle:
    """The result of fetching and cleaning a source."""

    url: str
    title: str
    text: str

    @property
    def word_count(self) -> int:
        return len(self.text.split())


class Fetcher(Protocol):
    """Anything that can turn a source string into a :class:`FetchedArticle`."""

    def fetch(self, source: str) -> FetchedArticle: ...

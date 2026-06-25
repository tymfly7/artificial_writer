"""Backwards-compatible shim for the fetcher refactor.

The fetcher logic moved into the :mod:`artificial_writer.core.fetchers` package.
This module re-exports the names that existing imports (the GUI and tests)
depend on, so nothing downstream had to change.
"""

from __future__ import annotations

from .fetchers.base import FetchedArticle
from .fetchers.html import HtmlFetcher, TextFetcher

__all__ = ["FetchedArticle", "HtmlFetcher", "TextFetcher"]

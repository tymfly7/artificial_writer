"""Pluggable fetchers behind a small registry.

The default :class:`HtmlFetcher` needs no optional dependencies; the PDF and
YouTube fetchers import their SDKs lazily so those extras stay optional.
"""

from __future__ import annotations

from . import registry
from .base import FetchedArticle, Fetcher
from .html import HtmlFetcher, TextFetcher

__all__ = ["FetchedArticle", "Fetcher", "HtmlFetcher", "TextFetcher", "registry"]

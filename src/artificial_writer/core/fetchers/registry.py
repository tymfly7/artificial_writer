"""Pick the right fetcher for a source URL.

The registry inspects the URL and dispatches to the matching fetcher: YouTube
links to :class:`YouTubeFetcher`, ``.pdf`` URLs to :class:`PdfFetcher`, and
everything else to :class:`HtmlFetcher`.
"""

from __future__ import annotations

from urllib.parse import urlparse

from ..errors import FetchError
from .base import FetchedArticle

_YOUTUBE_HOSTS = ("youtube.com", "youtu.be")


def _validate_scheme(source: str) -> None:
    parsed = urlparse((source or "").strip())
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise FetchError(f"Invalid URL: {source!r}. Use a full http(s):// address.")


def fetch(source: str, *, timeout: float = 30.0) -> FetchedArticle:
    """Fetch ``source`` using whichever fetcher its URL calls for."""
    _validate_scheme(source)
    parsed = urlparse(source.strip())
    host = parsed.netloc.lower()
    path = parsed.path.lower()

    if any(yt in host for yt in _YOUTUBE_HOSTS):
        from .youtube import YouTubeFetcher

        return YouTubeFetcher().fetch(source)

    if path.endswith(".pdf"):
        from .pdf import PdfFetcher

        return PdfFetcher(timeout=timeout).fetch(source)

    from .html import HtmlFetcher

    return HtmlFetcher(timeout=timeout).fetch(source)

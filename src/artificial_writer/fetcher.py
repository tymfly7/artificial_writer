"""Fetch readable article text from a web page.

The fetcher downloads a URL, strips boilerplate (scripts, nav, footers, ...),
and returns the main textual content. It is deliberately small and dependency
-light so it stays easy to test and reason about.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

from .errors import FetchError

logger = logging.getLogger(__name__)

# Tags that never contain article body text.
_BOILERPLATE_TAGS = ("script", "style", "noscript", "nav", "header", "footer", "aside", "form")

_DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (compatible; ArtificialWriter/1.0; +https://github.com/TymFly/artificial_writer)"
    )
}


@dataclass(frozen=True)
class FetchedArticle:
    """The result of fetching and cleaning a web page."""

    url: str
    title: str
    text: str

    @property
    def word_count(self) -> int:
        return len(self.text.split())


class TextFetcher:
    """Download a URL and extract its main readable text."""

    def __init__(self, timeout: float = 30.0, session: requests.Session | None = None) -> None:
        self._timeout = timeout
        self._session = session or requests.Session()

    @staticmethod
    def _validate_url(url: str) -> str:
        url = (url or "").strip()
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https") or not parsed.netloc:
            raise FetchError(f"Invalid URL: {url!r}. Use a full http(s):// address.")
        return url

    def fetch(self, url: str) -> FetchedArticle:
        """Fetch ``url`` and return its cleaned text.

        Raises:
            FetchError: if the request fails or no readable text is found.
        """
        url = self._validate_url(url)
        logger.info("Fetching %s", url)
        try:
            response = self._session.get(url, headers=_DEFAULT_HEADERS, timeout=self._timeout)
            response.raise_for_status()
        except requests.exceptions.RequestException as exc:
            raise FetchError(f"Failed to fetch {url}: {exc}") from exc

        return self._extract(url, response.text)

    @staticmethod
    def _extract(url: str, html: str) -> FetchedArticle:
        soup = BeautifulSoup(html, "lxml")

        for tag in soup(_BOILERPLATE_TAGS):
            tag.decompose()

        title = soup.title.get_text(strip=True) if soup.title else url

        paragraphs = [p.get_text(" ", strip=True) for p in soup.find_all("p")]
        text = "\n\n".join(p for p in paragraphs if p)

        # Fall back to the whole body if the page has no <p> tags.
        if not text and soup.body:
            text = soup.body.get_text(" ", strip=True)

        if not text.strip():
            raise FetchError(f"No readable text found at {url}.")

        return FetchedArticle(url=url, title=title, text=text)

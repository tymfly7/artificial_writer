"""Fetch and extract text from a PDF at a URL.

``pypdf`` is imported lazily so the ``pdf`` extra stays optional.
"""

from __future__ import annotations

import io
import logging
from urllib.parse import unquote, urlparse

import requests

from ..errors import FetchError
from .base import FetchedArticle

logger = logging.getLogger(__name__)

_DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (compatible; ArtificialWriter/1.0; +https://github.com/TymFly/artificial_writer)"
    )
}


class PdfFetcher:
    """Download a PDF and concatenate its page text."""

    def __init__(self, timeout: float = 30.0, session: requests.Session | None = None) -> None:
        self._timeout = timeout
        self._session = session or requests.Session()

    @staticmethod
    def _title_for(url: str) -> str:
        segment = unquote(urlparse(url).path.rstrip("/").rsplit("/", 1)[-1])
        return segment or url

    def fetch(self, url: str) -> FetchedArticle:
        """Fetch the PDF at ``url`` and return its extracted text.

        Raises:
            FetchError: if the download fails, parsing fails, or no text is found.
        """
        logger.info("Fetching PDF %s", url)
        try:
            response = self._session.get(url, headers=_DEFAULT_HEADERS, timeout=self._timeout)
            response.raise_for_status()
        except requests.exceptions.RequestException as exc:
            raise FetchError(f"Failed to fetch {url}: {exc}") from exc

        try:
            import pypdf
        except ImportError as exc:  # pragma: no cover - import guard
            raise FetchError(
                "The 'pypdf' package is not installed. Install it with "
                "`pip install artificial-writer[pdf]`."
            ) from exc

        try:
            reader = pypdf.PdfReader(io.BytesIO(response.content))
            text = "\n\n".join(page.extract_text() or "" for page in reader.pages)
        except Exception as exc:  # noqa: BLE001 - surface any parser error uniformly
            raise FetchError(f"Failed to parse PDF at {url}: {exc}") from exc

        if not text.strip():
            raise FetchError(f"No readable text found in PDF at {url}.")

        return FetchedArticle(url=url, title=self._title_for(url), text=text)
